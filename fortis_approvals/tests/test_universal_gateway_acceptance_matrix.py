"""Static invariants for the owner Fortis universal-gateway acceptance matrix.

These checks validate completeness and architectural intent of documentation,
NOT completion of Windows/Sonar/RDG/GitHub acceptance gates.
"""
from collections import Counter
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
MATRIX = (ROOT / 'fortis_approvals/deploy/'
          'FORTIS-UNIVERSAL-GATEWAY-ACCEPTANCE-MATRIX-20261101.md')
MASTER = ROOT / 'docs/guides/FORTIS-APPROVALS-SECURE-DEVELOPMENT.md'
README = ROOT / 'fortis_approvals/README.md'


class UniversalGatewayAcceptanceMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = MATRIX.read_text(encoding='utf-8')
        cls.rows = re.findall(r'^\|\s*([FAPSDO]-\d\d)\s*\|.+$',cls.text,re.M)
        cls.gates = re.findall(r'^\|\s*(M[0-8])\s*[—|].*$',cls.text,re.M)

    def test_exact_complete_unique_case_inventory(self):
        expected = {'F':4, 'A':14, 'P':12, 'S':10, 'D':13, 'O':13}
        self.assertEqual(len(self.rows),sum(expected.values()))
        self.assertEqual(len(self.rows),len(set(self.rows)))
        self.assertEqual(Counter(value[0] for value in self.rows),expected)
        for prefix, count in expected.items():
            self.assertEqual(
                {f'{prefix}-{i:02}' for i in range(1,count+1)},
                {row for row in self.rows if row.startswith(prefix+'-')})

    def test_release_gates_are_complete_and_no_live_claim(self):
        self.assertEqual(set(self.gates),{f'M{i}' for i in range(9)})
        self.assertEqual(len(self.gates),9)
        for text in (
            'FORTIS_UNIVERSAL_GATEWAY_PRODUCTION_ACCEPTANCE=OPEN',
            '**BLOCKED: реальный Sonar WRITE не разрешён**',
            'UNKNOWN/BLOCK',
            'WIN-A4',
            'G4-REAL',
            'IMAGE-R5',
            'OFFLINE',
            '**OPEN**',
            'PR/commit',
            'requestId',
        ):
            with self.subTest(text=text):
                self.assertIn(text,self.text)

    def test_four_combinations_and_no_generic_proxy(self):
        for text in (
            'F-01', 'F-02', 'F-03', 'F-04',
            'ALLOW', 'ASK', 'DENY',
            '*Сервисная авторизация*',
            '*machine client identity*',
            'Не общий интернет-прокси',
            'Fortis Repo',
            'Один Fortis',
            'без service token',
        ):
            self.assertIn(text,self.text)
        self.assertIn('не обязано',self.text)
        self.assertIn('токен **или** ASK',self.text)
        self.assertIn('authorized',self.text.lower())

    def test_owner_policy_and_rdgv1_exceptions_persist(self):
        for text in (
            'FREE→ASK', 'ASK→FREE',
            'RUN_APPROVAL',
            'IMPORT_APPROVAL',
            'Sonar WRITE',
            'SonarCloud',
            'GitHub',
            'RDG',
            'Repo1/Repo2',
            'сервисный токен',
            'WebAuthn',
            'токен не покидает Fortis',
        ):
            with self.subTest(text=text):
                self.assertIn(text,self.text)

    def test_master_and_readme_reference_matrix(self):
        name = MATRIX.name
        self.assertIn(name,MASTER.read_text(encoding='utf-8'))
        self.assertIn(name,README.read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
