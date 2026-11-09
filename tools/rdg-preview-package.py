#!/usr/bin/env python3
"""Export only the source files needed by the disposable Decision preview."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PYTHON_FILES=('rdg-preview','rdg-windows-lock','rdg-authority','rdg-transaction-io','rdg-portable',
    'rdg-portable-model','rdg-portable-store','rdg-portable-service','rdg-projection-cache','rdg-compact-read','rdg-scoped-read','rdg-batch','rdg-model-profiles','rdg-core-model',
    'rdg-decision-model','rdg-history-view','rdg-analysis','rdg-findings','rdg-questions','rdg-dependency-policies','rdg-recommendations','rdg-package-transfer','rdg-legacy-migration',
    'rdg-workflow-commands','rdg-loopback-helper')
ENTRY='RDG-Decision-Preview'
README='''RDG Decision — ручная проверка

1. Извлеките весь архив в обычную папку. Не запускайте .cmd внутри ZIP.
2. Нужны установленный Python 3 (проверен 3.11) и Node.js 18+ с командой node в PATH.
3. Дважды нажмите Start-Decision-Preview.cmd. Первый запуск создаст venv и установит tzdata.
4. Откроется полноэкранный Explorer настоящего Decision Viewer. Выберите процесс «Ручная проверка Decision».
   Рабочие области находятся внутри процесса; готовые графы и пакеты — в своих разделах.
   Tampermonkey и регистрация ключа для этой песочницы не нужны.
5. Оставьте консоль открытой. Остановка — Ctrl+C. Следующий запуск продолжает те же данные.

Тестовые данные: %LOCALAPPDATA%\\RDG-DecisionPreview\\data
Порт: 8795 на 127.0.0.1. Точный URL сессии появляется в консоли; он меняется при новом запуске.
Если браузер не открылся автоматически, откройте показанный URL вручную.
При ошибке окно консоли останется открытым. Занятый порт автоматически не освобождается.

Короткая проверка:
— «+ Блок»: создайте Decision с названием, описанием и основанием; «Добавить блок» → «Сохранить».
— «Добавить план во времени» → «Сохранить»; разместите этот Decision без даты и выбора selected.
— Перетащите блок, дождитесь «Позиция сохранена», остановите и снова запустите .cmd.
  Проверьте сохранённые блок, Plan и позицию. Начальные камера/вкладки относятся к новой сессии.
— Откройте Explorer кнопкой «RDG Viewer»: «Процесс-графы» → процесс → рабочие области.
  Process Graph владеет блоками, Plan и History. Working Graph — область по ссылкам на них.
  Новый процесс начинается без областей. «+ Новая рабочая область» задаёт её состав.
  Блок, добавленный из области, входит в неё; добавление в полный процесс не меняет состав областей.
— «Готовые графы» → «Основы RDG» → «Графы линз»: проверьте 11 отдельных линз.

Обновление с предыдущего preview:
— Остановите старую консоль Ctrl+C. Распакуйте эту сборку в новую папку build-20261029-fix2.
— Launcher использует прежнюю папку данных. Сохранённые Graph/Plan и позиции остаются.
— Прежняя автоматически созданная Main work сохраняется как обычная рабочая область.
  Новые процессы и новые блоки в полном процессе больше не создают и не наполняют её.
— Внизу нового экрана указано «Decision UI · 20261029-fix2».

Архив содержит код, определения линз и BUILD.json с SHA256 файлов. Рабочие Graph/Plan,
история пользователя, Authority/grants, credentials и настройки исходной среды в него не входят.
Песочница сама создаёт собственные тестовые права только для своего namespace.
Это сборка для ручной проверки, не установленный защищённый production-контур.
Результат на пользовательском Windows фиксируется после ручного запуска.
'''

def build(output):
    output=Path(output)
    if output.exists():raise ValueError('OUTPUT_EXISTS')
    if output.suffix.lower()!='.zip':raise ValueError('ZIP_REQUIRED')
    files=[Path('Start-Decision-Preview.cmd'),Path('tools/requirements-decision-preview.txt')]
    files += [Path('tools')/(name+'.py') for name in PYTHON_FILES]
    files += [Path('tools')/name for name in ('rd-graph-viewer.user.js','rdg-layout-cli.cjs','rdg-layout-core.js','rdg-visual-projection.js')]
    files += sorted(p.relative_to(ROOT) for p in (ROOT/'tools/rdg-agent-lenses').glob('*.json'))
    files += sorted(p.relative_to(ROOT) for p in (ROOT/'tools/contracts').glob('*.json'))
    payload={}
    for relative in files:
        path=ROOT/relative
        if not path.is_file() or path.is_symlink():raise ValueError('SOURCE_FILE_REQUIRED:'+str(relative))
        payload[relative.as_posix()]=path.read_bytes()
    try:head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip()
    except (OSError,subprocess.CalledProcessError):head=None
    manifest={'schemaVersion':1,'kind':'rdg-decision-manual-build','profile':'rdg-decision-v1',
        'entryPoint':'Start-Decision-Preview.cmd','uiBuild':'decision-desktop-20261103-workareas','repositoryHead':head,'includesUserData':False,
        'sourceFiles':{name:hashlib.sha256(raw).hexdigest() for name,raw in sorted(payload.items())}}
    payload['BUILD.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
    payload['README.txt']=README.replace('\n','\r\n').encode('utf8')
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for name,raw in sorted(payload.items()):archive.writestr(ENTRY+'/'+name,raw)
    return {'path':str(output),'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'files':len(payload),'includesUserData':False}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(build(parser.parse_args().output)))
if __name__=='__main__':main()
