"""One-way synthetic owner decision -> separate fake write worker PROCESS."""
from multiprocessing import get_context
from pathlib import Path
import tempfile

from fortis_approvals.core import Authenticator, Core
from fortis_approvals.owner_auth import OwnerWebAuthn
from fortis_approvals.owner_portal import OwnerPortal
from fortis_approvals.g4_candidate import NoWriteTransport
from fortis_approvals.g4_write_lab import (LAB_OPERATION, LabSonar,
    LabOwnerProposalCoreMixin, lab_worker_once)
from fortis_approvals.sonar import SonarIssueAdapter
from test_g4_write_lab import GuardedWriteLabTests
from test_g4_write_security import G4VirtualKey, ORIGIN


class ProcessOnlyOwnerCore(LabOwnerProposalCoreMixin,Core):
    """Privileged dispatch absent in owner process; no real network available."""


class G4IsolatedLabWorkerTests(GuardedWriteLabTests):
    """Reuse test-only WebAuthn/owner helper, replace Core adapter with GET-only."""
    def setUp(self):
        tmp=tempfile.TemporaryDirectory(prefix='g4-split-process-lab-')
        self.addCleanup(tmp.cleanup)
        folder=Path(tmp.name)
        self.core_db=folder/'requests.sqlite'
        self.remote=LabSonar()
        self.fake_owner_read=self.remote
        self.owner=OwnerWebAuthn(folder/'owner.sqlite',origin=ORIGIN)
        self.core=ProcessOnlyOwnerCore(self.core_db,adapters={},
                  policies={LAB_OPERATION:'ASK'},
                  authenticator=Authenticator({'lab-proposer':'lab-actor'}),
                  owner_verifier=self.owner)
        self.adapter=SonarIssueAdapter(NoWriteTransport(self.remote),
                  project_keys=('g4-lab-project',),
                  receipt_store=folder/'owner-get-only.sqlite')
        self.core.adapters['sonarcloud']=self.adapter
        self.portal=OwnerPortal(self.core,self.owner,strong_operations={LAB_OPERATION})
        self.worker_receipts=folder/'worker-receipts.sqlite'
        self.key=G4VirtualKey()
        self.cookie=None
        self.csrf=None

    def launch_worker(self,request_id):
        ctx=get_context('spawn')
        output=ctx.Queue()
        proc=ctx.Process(target=lab_worker_once,
           args=(str(self.core_db),str(self.worker_receipts),request_id,output))
        proc.start()
        proc.join(timeout=20)
        if proc.is_alive():
            proc.terminate();proc.join(5)
            self.fail('LAB_WORKER_HUNG')
        self.assertEqual(proc.exitcode,0)
        return output.get(timeout=4)

    def test_owner_process_approve_writes_no_sonar_until_separate_worker(self):
        row=self.propose();self.login()
        code,owner_result,_=self.decide(row)
        self.assertEqual((code,owner_result['state']),(200,'APPROVED'))
        self.assertEqual(self.fake_owner_read.posts,0)
        self.assertEqual(self.core._read(row['requestId'])['state'],'APPROVED')
        ipc=self.launch_worker(row['requestId'])
        self.assertEqual(ipc,{'state':'EXECUTED','fake_posts':1})
        self.assertEqual(self.core._read(row['requestId'])['state'],'EXECUTED')
        self.assertEqual(self.launch_worker(row['requestId'])['fake_posts'],0)
        self.assertEqual([r[0] for r in self.reservations()], [row['requestId']])

    def test_pending_and_rejected_requests_never_dispatch_from_worker(self):
        pending=self.propose()
        self.assertEqual(self.launch_worker(pending['requestId']),
                         {'state':'PENDING','fake_posts':0})
        self.login()
        code,rejected,_=self.decide(pending,'reject')
        self.assertEqual((code,rejected['state']),(200,'REJECTED'))
        self.assertEqual(self.launch_worker(pending['requestId']),
                         {'state':'REJECTED','fake_posts':0})
        self.assertEqual(self.fake_owner_read.posts,0)
        self.assertEqual(self.reservations(),[])

    def test_owner_process_direct_unsafe_core_execute_cannot_call_fake_post(self):
        row=self.propose();self.login()
        code,approved,_=self.decide(row)
        self.assertEqual((code,approved['state']),(200,'APPROVED'))
        # Bypass mixin and call base Core.execute in the owner PROCESS.
        # It has NoWriteTransport and must not mutate the fake resource.
        result=Core.execute(self.core,row['requestId'])
        self.assertEqual(result['state'],'UNCERTAIN')
        self.assertEqual(self.fake_owner_read.posts,0)
        # Owner bypass consumes dispatch marker: no retry even in worker.
        self.assertEqual(self.launch_worker(row['requestId']),
                         {'state':'UNCERTAIN','fake_posts':0})


# Avoid rerunning all inherited GuardedWriteLabTests tests in the subclass:
for _name in tuple(n for n in vars(GuardedWriteLabTests) if n.startswith('test_')):
    setattr(G4IsolatedLabWorkerTests,_name,None)


def load_tests(loader, tests, pattern):
    # Imported fixture TestCase has its own module; run only this module's 3 cases.
    return loader.loadTestsFromTestCase(G4IsolatedLabWorkerTests)
