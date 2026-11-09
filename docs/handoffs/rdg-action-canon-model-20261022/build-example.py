from __future__ import annotations

import json
import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor

ROOT = Path(__file__).resolve().parent
OUT = ROOT
QA = ROOT / 'tmp' / 'rdg-diagram'
OUT.mkdir(exist_ok=True)
QA.mkdir(parents=True, exist_ok=True)
W, H = 1800, 1180

FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
pdfmetrics.registerFont(TTFont('RDG', FONT))
pdfmetrics.registerFont(TTFont('RDG-Bold', BOLD))

C = {
    'bg': '#F7F8FC', 'ink': '#17263E', 'muted': '#58677D',
    'line': '#77879B', 'panel': '#FFFFFF', 'border': '#D9E0EB',
    'R': ('#EAF2FF', '#3775CB'), 'A': ('#FFF1DA', '#BE7A12'),
    'Context': ('#E4F5F2', '#278C81'), 'Canon': ('#F1EAFB', '#8556BB'),
    'Info': ('#EEF1F6', '#7B8798'), 'Evidence': ('#E7F5EA', '#37905A'),
    'QRPE': ('#FFF0EA', '#C66B40'), 'good': '#27814D', 'bad': '#BE4855',
    'blue': '#3775CB', 'purple': '#8556BB', 'teal': '#278C81',
}

PAGES = [
    ('map', '00 Карта и обозначения', 'Карта примера и переходов', 'Целевая модель RDG - учебный пример, а не описание реализованного API.'),
    ('overview', '01 Общая картина', 'Связи одной работы - разные собственные графы', 'Это обзор связей, а не собственный граф R0. Фокусные графы раскрываются на отдельных страницах.'),
    ('r1', '02 Граф R1', 'Граф цели R1: заявки не теряются', 'В фокусе цель, её происхождение и способы реализации. Выходы способов раскрываются в графах Actions.'),
    ('r2', '03 Граф R2', 'Граф цели R2: понятный статус', 'Несколько способов могут дополнять друг друга. Общий Action имеет одно состояние.'),
    ('aservice', '04 Граф A-SERVICE', 'Собственный граф Action: A-SERVICE', 'Ситуация Action: относящиеся R с явными ролями и Context. Каноны - примеры для оценки.'),
    ('canon', '05 Смешанный канон', 'Граф канона: единый сервис', 'Канонические R и контексты описывают сопоставляемую ситуацию, а не факты проекта.'),
    ('negative', '06 Отрицательный канон', 'Граф канона: только аргументы против', 'Отрицательная ситуация может требовать совместного выполнения нескольких условий.'),
    ('compare', '07 Сопоставление', 'От канона к реальным блокам', 'Ситуация Action сравнивается с канонами. Выводы и основания относятся к реальным рабочим инстансам.'),
    ('rin', '08 Граф R-IN', 'Граф выходной цели R-IN', 'Происхождение, роль подцели, фактический результат и отдельное закрытие.'),
    ('ratt', '09 Граф R-ATT', 'Граф принятой цели: необходимость пересмотрена', 'R-ATT была обязательной. Позднее оформлен отдельный исход «не требуется».'),
    ('awaive', '10 Граф A-NEED', 'Action проверки необходимости цели', 'Результат проверки может подтвердить необходимость или обосновать исход «не требуется».'),
    ('anotify', '11 Граф A-NOTIFY', 'Собственный граф ещё не выбранного Action', 'На бумаге допустимы способы, будущие R, каноны и Findings без обязательств и выполнения.'),
    ('rnotify', '12 Граф R-NOTIF', 'Взаимоисключение внутри собственной цели', 'Выбор способа внутри R не превращает выходы исходного Action в необязательные.'),
    ('materials', '13 Информация и Evidence', 'Пояснение и подтверждение - разные роли', 'Один информационный объект или Evidence может быть связан с несколькими сущностями.'),
    ('closure', '14 Закрытие и блокировки', 'Снятие блокировок не закрывает родителя', 'Открытые обязательные R блокируют. Закрытие требует отдельного подтверждённого результата.'),
    ('plan', '15 План во времени', 'Бумажный граф и временной Plan', 'Plan задаёт размещение и порядок. Он ссылается на те же экземпляры R/A.'),
    ('history', '16 История и identity', 'Единая история общего Action', 'Факты не восстанавливаются задним числом из текущего рисунка.'),
    ('lens', '17 Базовая линза', 'Линза: управляемая работа с ИИ через RDG', 'Граф инструкции: цели работы, выбор содержания для бумаги, правила построения и рабочие факты.'),
    ('retention', '18 Канон нанесения', 'Канон: наносить ли фрагмент на бумагу', '(C1 OR C2) AND C3. В центре - тот же A-L-SAVE, который проверяется этим каноном.'),
    ('drawchoice', '19 Граф R-L-PAPER', 'Граф цели: оправданный состав бумаги', 'Решаем, наносить ли конкретный фрагмент вообще. Это не выбор режима хранения файла.'),
    ('adraw', '20 Граф A-L-SAVE', 'Action нанесения фрагмента на бумагу', 'Ситуация Action и рассматриваемый канон вместе входят в область оценки этого Action.'),
    ('rules', '21 Граф R-L-SEM', 'Собственный граф R-L-SEM', 'Здесь цель и способ её реализации. Выходы A-L-MODEL раскрываются в собственном графе этого Action.'),
    ('workflow', '22 Графы целей работы', 'Графы целей: контекст и способы', 'Варианты действий показаны у целей. Их выходные R находятся в собственных графах этих Actions.'),
    ('catalog', '23 Каталог линз', 'Каталог и выбор применимых графов линз', 'Перед работой просматриваются доступные линзы; пользователь может прямо указать нужные.'),
    ('boundaries', '24 Границы графов', 'Где заканчивается каждый собственный граф', 'Граф R: на Actions или под-R. Граф Action: на его выходных R. Граф канона: на проверяемом Action.'),
    ('amodel', '25 Граф A-L-MODEL', 'Собственный граф A-L-MODEL', 'Здесь раскрываются обязательные требования способа построения, а не в графе исходной R-L-SEM.'),
    ('wmethods', '26 Графы рабочих Actions', 'Собственные графы рабочих Actions', 'Два отдельных фокуса Action; все показанные выходы пока на бумаге и станут обязательными при выборе своего A.'),
    ('aselect', '27 Граф A-L-SELECT', 'Собственный граф выбора линз', 'Входящие требования, общий Action и его выходная R. Из графа цели сюда переходят по ссылке на Action.'),
    ('canonmodes', '28 Условия канона', 'Условие канона - пример для сравнения', 'Смысл, группа, свойство или конкретно описанный случай. Канон самодостаточен и не ссылается на рабочие инстансы.'),
    ('canonpattern', '29 Канон-шаблон', 'Самодостаточный канон и текущая проверка', 'Условия хранятся внутри канона. Текущая проверка показывает тот же Action, без сохранённой внешней ссылки из канона.'),
    ('patternmatch', '30 Реальные зависимости', 'Сопоставление и реальные зависимости Action', 'Исполнитель сравнивает показательный канон с реальными R/контекстами. Движок отслеживает реальные зависимости.'),
    ('rolecheck', '31 Линза: R и Actions', 'Линза: требование выражает результат, Action - способ', 'Собственный граф R-L-ROLE: проверяем смысл блоков, а не только допустимость их JSON.'),
    ('canoncheck', '32 Линза: канон и QRPE', 'Линза: сопоставление и результаты проверки', 'Два собственных графа R. Канонический пример, фактический инстанс, вывод и QRPE имеют разные роли.'),
    ('linkrules', '33 Линза: связи и состояния', 'Линза: связи, состояния и разрешённые типы', 'Каждый фокус R заканчивается своим Action. Правила вынесены в информационные пояснения.'),
    ('factswork', '34 Линза: факты работы', 'Собственный граф R-L-FACTS', 'Цель работы и непосредственные под-R. Планирование, история и подтверждение результата раскрываются отдельно.'),
    ('historygoal', '35 Граф R-L-HISTORY', 'Собственный граф R-L-HISTORY', 'Происхождение цели, способ проверки и достаточность истории.'),
    ('evidencegoal', '36 Граф R-L-EVIDENCE', 'Собственный граф R-L-EVIDENCE', 'Происхождение цели и способ проверить утверждение в его области.'),
    ('truth', '37 Истинность и повтор', 'R: требуемая истинность и повторное открытие', 'Это последовательные снимки одной R, а не разные независимо изменяемые экземпляры.'),
    ('stalechain', '38 Пересмотр цепочки', 'Изменение R1 и проверка всей зависимой работы', 'Один рабочий scope и общий A; stale означает необходимость проверки актуальности.'),
    ('strength', '39 Сила канона', 'Жёсткая несовместимость и мягкий довод против', 'Сила довода отделена от доказанности; для AND проверяется вся группа.'),
    ('decompose', '40 Подробность R', 'Подробная R и полезная декомпозиция', 'Два учебных варианта уточнения. Они не изменяют основной снимок сервиса автоматически.'),
    ('workscopes', '41 Рабочие графы', 'Рабочие графы: общая или независимая работа', 'Рабочий граф - scope работы. Собственные графы R/A/канона - представления сущностей этого scope.'),
    ('originrecord', '42 Запись происхождения', 'Как записать происхождение выхода общего Action', 'Поле origin в INTRODUCES согласует исходные цели, блокировки и границы собственных графов.'),
]
PAGE_IDS = {k: f'rdg-{k}-20261021' for k, *_ in PAGES}

def page_reference(key):
    index = [p[0] for p in PAGES].index(key)
    return f'PDF стр. {index+1} / вкладка {index:02d}'


@dataclass
class Entity:
    kind: str
    title: str
    state: str = ''
    home: str | None = None
    candidate: bool = False


E = {
    'R0': Entity('R', 'Сервис заявок полезен и управляем', 'Принята / открыта', 'overview'),
    'R1': Entity('R', 'Заявки регистрируются без потерь', 'Принята / открыта', 'r1'),
    'R2': Entity('R', 'Заявителю понятен статус заявки', 'Принята / открыта', 'r2'),
    'R-PRIV': Entity('R', 'Персональные данные защищены', 'Реальное ограничение'),
    'R-OFFLINE': Entity('R', 'Работа доступна в закрытой сети', 'Реальное ограничение'),
    'R-IN': Entity('R', 'Заявка сохраняется после перезапуска', 'Принята / закрыта', 'rin'),
    'R-TRACK': Entity('R', 'Текущий статус виден заявителю', 'Принята / открыта'),
    'R-SEC': Entity('R', 'Права доступа корректны', 'Принята / открыта'),
    'R-ATT': Entity('R', 'К заявке можно приложить файл', 'Принята / НЕ ТРЕБУЕТСЯ', 'ratt'),
    'R-NOTIF': Entity('R', 'Заявитель получает уведомление', 'На бумаге / не принята', 'rnotify', True),
    'A-SERVICE': Entity('A', 'Создать единый сервис заявок', 'Выбран / открыт', 'aservice'),
    'A-MANUAL': Entity('A', 'Вести реестр заявок вручную', 'Кандидат'),
    'A-HISTORY': Entity('A', 'Показывать историю статуса', 'Кандидат', candidate=True),
    'A-NOTIFY': Entity('A', 'Уведомлять об изменении', 'Кандидат', 'anotify', True),
    'A-GUIDE': Entity('A', 'Объяснять значения статусов', 'Кандидат', candidate=True),
    'A-NEED': Entity('A', 'Проверить необходимость вложений', 'Выбран / закрыт', 'awaive'),
    'A-EMAIL': Entity('A', 'Уведомлять по email', 'Кандидат', candidate=True),
    'A-MSG': Entity('A', 'Уведомлять в мессенджере', 'Кандидат', candidate=True),
    'C-TEAM': Entity('Context', 'Команда умеет развивать сервис', 'Факт / версия v1'),
    'C-OPS': Entity('Context', 'Владелец эксплуатации не назначен', 'Факт / версия v1'),
    'C-HOST': Entity('Context', 'Сервис работает внутри закрытой сети', 'Факт проверки / версия v1'),
    'C-PROCESS': Entity('Context', 'В текущем процессе нет файлов', 'Факт / версия v1'),
    'C-NEED-BEFORE': Entity('Context', 'Польза вложений для R1/R2 ещё не проверена', 'Основание выбора / момент t3'),
    'C-CONTACT': Entity('Context', 'Канал связи ещё не подтверждён', 'Неизвестное'),
    'CAN-SERVICE': Entity('Canon', 'Когда оправдан единый сервис', 'Положительные и отрицательные условия', 'canon'),
    'CAN-EXTERNAL': Entity('Canon', 'Закрытая сеть и внешняя зависимость', 'Только отрицательная ситуация', 'negative'),
    'CAN-NEED': Entity('Canon', 'Когда проверять необходимость цели', 'Канонические условия', 'awaive'),
    'CAN-NOTIFY': Entity('Canon', 'Когда полезны уведомления', 'Каноническая ситуация', 'anotify'),
    'I-ARCH': Entity('Info', 'Устройство сервиса и термины', 'Общее пояснение / v1', 'materials'),
    'I-PROCESS': Entity('Info', 'Описание процесса заявок', 'Материал исследования / v1', 'materials'),
    'E-REG': Entity('Evidence', 'Заявка восстановлена после перезапуска', 'Утверждение + область + версия', 'materials'),
    'E-ATT': Entity('Evidence', 'Файлы процессу не требуются', 'Утверждение + область + версия', 'awaive'),
    'F-OPS': Entity('QRPE', 'Риск: нет владельца эксплуатации', 'Открыт / до выбора обнаружен', 'compare'),
    'F-CHANNEL': Entity('QRPE', 'Уточнить доступный канал связи', 'Открыт / кандидат', 'anotify'),
    'R-LENS': Entity('R', 'Работа с участием ИИ ведётся через RDG', 'Цель рабочей линзы', 'lens'),
    'R-L-CONTEXT': Entity('R', 'Цели и важный контекст уточнены', 'Требование линзы', 'workflow'),
    'R-L-OPTIONS': Entity('R', 'Варианты исследованы и сопоставлены', 'Требование линзы', 'workflow'),
    'R-L-PAPER': Entity('R', 'Состав графа на бумаге оправдан его ценностью', 'Требование линзы', 'drawchoice'),
    'R-L-FACTS': Entity('R', 'Состояния и основания работы прослеживаются', 'Требование линзы', 'factswork'),
    'A-L-SAVE': Entity('A', 'Нанести этот фрагмент на бумагу', 'Выбран / открыт', 'adraw'),
    'A-L-SKIP': Entity('A', 'Не наносить этот фрагмент на бумагу', 'Кандидат', candidate=True),
    'CAN-KEEP': Entity('Canon', 'Когда наносить фрагмент на бумагу', '(C1 OR C2) AND C3', 'retention'),
    'C-L-C1': Entity('Context', 'Есть обоснованное решение об общем A для R1/R2', 'Фактическое основание / v1'),
    'C-L-C2': Entity('Context', 'Есть полезное разбиение с явным происхождением R', 'Фактическое основание / v1'),
    'C-L-C3': Entity('Context', 'Повторная польза фрагмента оправдывает сопровождение', 'Оценка ценности и затрат / v1'),
    'R-L-SEM': Entity('R', 'Фрагмент построен по правилам системы', 'Принята / открыта', 'rules'),
    'A-L-MODEL': Entity('A', 'Построить и проверить фрагмент', 'Выбран / открыт', 'amodel'),
    'I-L-RULES': Entity('Info', 'Назначение типов и правила связей', 'Общий информационный объект / v1', 'rules'),
    'R-L-ROLE': Entity('R', 'R и Actions выражают цели и способы', 'Принята / открыта', 'rolecheck'),
    'R-L-LINK': Entity('R', 'Происхождение R и ситуации Actions явны', 'Принята / открыта', 'linkrules'),
    'R-L-STATE': Entity('R', 'Бумага, выбор и выполнение различимы', 'Принята / открыта', 'linkrules'),
    'R-L-TYPES': Entity('R', 'Использованы только доступные типы', 'Принята / открыта', 'linkrules'),
    'R-L-CANONS': Entity('R', 'Оценки Actions по ситуациям и канонам обоснованы', 'Принята / открыта', 'canoncheck'),
    'R-L-QRPE': Entity('R', 'Результаты проверки и существенные QRPE прослеживаются', 'Принята / открыта', 'canoncheck'),
    'A-L-CLARIFY': Entity('A', 'Уточнить цели и исходные данные', 'Кандидат', 'wmethods', True),
    'A-L-EXPLORE': Entity('A', 'Исследовать и сравнить способы', 'Кандидат', 'wmethods', True),
    'R-L-LENSES': Entity('R', 'Для работы определены подходящие линзы', 'Требование контекста', 'catalog'),
    'A-L-SELECT': Entity('A', 'Выбрать линзы и учесть их требования', 'Кандидат', 'aselect', True),
    'R-L-USER': Entity('R', 'Указанная пользователем линза применена', 'Пример входящего требования'),
    'I-L-CATALOG': Entity('Info', 'Каталог доступных графов линз', 'Назначение / область / версия / ссылка', 'catalog'),
    'CAN-ACCOUNT': Entity('Canon', 'Когда полезен общий учёт объектов', 'Самодостаточный пример', 'canonpattern'),
    'A-L-CHECK-RA': Entity('A', 'Проверить смысл R и Actions', 'Кандидат', candidate=True),
    'A-L-BIND': Entity('A', 'Сравнить канон с ситуацией A', 'Кандидат', candidate=True),
    'A-L-FINDINGS': Entity('A', 'Проверить и оформить QRPE', 'Кандидат', candidate=True),
    'A-L-LINKS': Entity('A', 'Проверить происхождение и ситуации', 'Кандидат', candidate=True),
    'A-L-STATES': Entity('A', 'Сверить состояния с фактами', 'Кандидат', candidate=True),
    'A-L-KINDS': Entity('A', 'Сверить типы с доступной моделью', 'Кандидат', candidate=True),
    'R-L-HISTORY': Entity('R', 'История изменений и оснований прослеживается', 'Требование линзы', 'historygoal'),
    'R-L-EVIDENCE': Entity('R', 'Выводы о результате подтверждены в своей области', 'Требование линзы', 'evidencegoal'),
}
E['A-MANUAL'].candidate = True


def width(s, size, bold=False):
    return pdfmetrics.stringWidth(s, 'RDG-Bold' if bold else 'RDG', size)


def wrap(s, max_width, size, bold=False):
    out = []
    for para in s.split('\n'):
        words = para.split()
        if not words:
            out.append('')
            continue
        line = ''
        for word in words:
            trial = (line + ' ' + word).strip()
            if width(trial, size, bold) <= max_width:
                line = trial
            else:
                if line:
                    out.append(line)
                if width(word, size, bold) > max_width:
                    raise ValueError(f'Unbreakable word {word!r} needs {width(word,size,bold):.1f}, got {max_width}')
                line = word
        out.append(line)
    return out


class Page:
    def __init__(self, key):
        self.key = key
        self.index = [p[0] for p in PAGES].index(key)
        self.spec = PAGES[self.index]
        self.items = []
        self.nodes = {}
        self.serial = 0
        self.header()

    def uid(self, prefix='c'):
        self.serial += 1
        return f'{self.key}-{prefix}{self.serial}'

    def shape(self, x, y, w, h, fill='#FFFFFF', stroke=None, sw=1.5, kind='rect', dashed=False,
              link=None, entity=None, parent=None, layer='foreground'):
        uid = self.uid('s')
        self.items.append(dict(type='shape', id=uid, x=x, y=y, w=w, h=h, fill=fill,
                               stroke=stroke, sw=sw, kind=kind, dashed=dashed,
                               link=link, entity=entity, parent=parent, layer=layer))
        return uid

    def text(self, text, x, y, w, h=None, size=19, bold=False, color=None,
             align='left', leading=None, parent=None, link=None):
        lines = wrap(text, w, size, bold)
        leading = leading or size * 1.28
        needed = len(lines) * leading
        if h is not None and needed > h + 0.01:
            raise ValueError(f'{self.key}: text overflow {needed:.1f}>{h}: {text!r}')
        if x < 0 or y < 0 or x+w > W+0.1 or y+needed > H+0.1:
            raise ValueError(f'{self.key}: out of bounds {text!r}')
        for i, line in enumerate(lines):
            self.items.append(dict(type='text', id=self.uid('t'), text=line, x=x, y=y+i*leading,
                                  w=w, h=leading, size=size, bold=bold, color=color or C['ink'],
                                  align=align, parent=parent, link=link))
        return needed

    def label(self, text, x, y, w=220, color=None, size=16, fill=None):
        lines = wrap(text, w-16, size)
        h = len(lines)*size*1.28 + 10
        self.shape(x, y, w, h, fill or C['bg'], None, kind='round')
        self.text(text, x+8, y+5, w-16, size=size, color=color or C['muted'])
        return h

    def panel(self, x, y, w, h, title=None, fill=None, color=None, dashed=False):
        uid=self.shape(x, y, w, h, fill or C['panel'], color or C['border'], kind='round', dashed=dashed,layer='background')
        if title:
            self.text(title, x+22, y+18, w-44, size=20, bold=True, color=color or C['ink'])
        return dict(id=uid,x=x,y=y,w=w,h=h)

    def note(self, title, body, x, y, w, h=120, color=None, fill=None, link=None):
        uid=self.shape(x,y,w,h, fill or '#FFFFFF', color or C['border'], kind='round',link=link)
        th=self.text(title,x+20,y+15,w-40,size=19,bold=True,parent=uid)
        by=15+th+11
        self.text(body,x+20,y+by,w-40,h=h-by-14,size=17,color=C['muted'],parent=uid)
        return uid

    def node(self, entity, x,y,w=300,h=150, title=None, state=None, home=None,
             kind=None, candidate=None, canonical=False):
        if entity in E:
            e=E[entity]
        else:
            e=Entity(kind or 'R',title or entity,state or '',home,candidate or False)
        kind=kind or e.kind
        fill,stroke=C.get(kind,C['R'])
        if canonical:
            fill = '#F7F1FC' if kind=='R' else fill
        candidate = e.candidate if candidate is None else candidate
        state=e.state if state is None else state
        home=e.home if home is None else home
        title=title or e.title
        link=home if home != self.key else None
        closed = 'закрыт' in state.lower() and 'не закрыт' not in state.lower()
        unnecessary = 'НЕ ТРЕБУЕТСЯ' in state
        if closed: stroke=C['good']
        if unnecessary: stroke='#718096';fill='#EFF2F7'
        if kind=='A':
            h=w
            shape='ellipse'
            tw=w*.76
            fs=18
            title_lines=wrap(title,tw,fs,True)
            if len(title_lines)>4:
                raise ValueError(f'Action title too long: {entity}: {title_lines}')
            main_h=len(title_lines)*23
            id_y=y+h*.17
            title_y=y+h*.37-(max(0,len(title_lines)-2)*8)
            state_fs=13.5
            state_w=w*.80
            state_lines=wrap(state,state_w,state_fs)
            state_y=y+h*.76
            if title_y+main_h > state_y-4:
                title_y=state_y-main_h-7
        else:
            shape='round' if kind!='R' else 'rect'
            tw=w-32
            fs=19.5
            title_lines=wrap(title,tw,fs,True)
            id_y=y+12
            title_y=y+39
            main_h=len(title_lines)*25
            state_fs=14
            state_w=w-32
            state_lines=wrap(state,state_w,state_fs)
            state_y=y+h-14-len(state_lines)*18
            if title_y+main_h > state_y-7:
                raise ValueError(f'{self.key}: node overflow {entity}; title={title_lines}, state={state_lines}, h={h}')
        uid=self.shape(x,y,w,h,fill,stroke,3 if kind=='A' and not candidate else 1.8,shape,candidate,
                       link,entity)
        box=dict(id=uid,x=x,y=y,w=w,h=h,entity=entity)
        self.nodes[entity]=box
        self.text(entity,x+(w-tw)/2,id_y,tw,size=13,bold=True,color=stroke,
                  align='center' if kind=='A' else 'left',parent=uid)
        self.text(title,x+(w-tw)/2,title_y,tw,size=fs,bold=True,leading=23 if kind=='A' else 25,
                  align='center' if kind=='A' else 'left',parent=uid)
        if state:
            self.text(state,x+(w-state_w)/2,state_y,state_w,size=state_fs,leading=18,
                      align='center' if kind=='A' else 'left',parent=uid,
                      color=C['good'] if closed else C['muted'])
        if link:
            self.text('↗',x+w-29,y+10,20,size=19,bold=True,color=stroke,parent=uid)
        return box

    def custom(self, id,kind,title,x,y,w=300,h=150,state='',**kw):
        return self.node(id,x,y,w,h,title=title,state=state,kind=kind,**kw)

    def edge(self, source, target, s='bottom', t='top', via=None, color=None, dashed=False,
             arrow=True, label=None, lx=None, ly=None, lw=220):
        a=self.nodes[source] if isinstance(source,str) else source
        b=self.nodes[target] if isinstance(target,str) else target
        def anchor(n,side):
            if isinstance(side,tuple): return (n['x']+n['w']*side[0], n['y']+n['h']*side[1])
            return {'top':(n['x']+n['w']/2,n['y']), 'bottom':(n['x']+n['w']/2,n['y']+n['h']),
                    'left':(n['x'],n['y']+n['h']/2), 'right':(n['x']+n['w'],n['y']+n['h']/2)}[side]
        points=[anchor(a,s)]+(via or [])+[anchor(b,t)]
        self.items.append(dict(type='edge',id=self.uid('e'),source=a['id'],target=b['id'],
                               points=points,color=color or C['line'],dashed=dashed,arrow=arrow))
        if label:
            if lx is None or ly is None: raise ValueError('Explicit label placement required')
            self.label(label,lx,ly,lw,color=color)

    def header(self):
        _,_,title,subtitle=self.spec
        self.shape(0,0,W,134,'#FFFFFF',None,layer='background')
        self.text('RDG / ВИЗУАЛЬНАЯ МОДЕЛЬ',54,22,1100,size=13,bold=True,color=C['muted'])
        self.text(title,54,48,1440,size=31,bold=True)
        self.text(subtitle,54,96,1675,size=17,color=C['muted'])
        self.shape(0,H-60,W,60,'#FFFFFF',None,layer='background')
        self.text('Учебный пример / целевая модель / состояния и источники условные',54,H-38,1330,size=13,color=C['muted'])
        self.text(f'{self.index+1:02d} / {len(PAGES):02d}',1635,H-39,110,size=14,bold=True,align='right')
        self.nav('Карта', 'map', 1500, 26, 92)
        if self.index:
            self.nav('←',PAGES[self.index-1][0],1605,26,55)
        if self.index<len(PAGES)-1:
            self.nav('→',PAGES[self.index+1][0],1672,26,55)

    def nav(self,title,dest,x,y,w=250,h=37):
        uid=self.shape(x,y,w,h,'#F0F3F8',C['border'],kind='round',link=dest)
        self.text(title,x+10,y+8,w-20,size=15,bold=True,color=C['blue'],align='center',parent=uid)

    def section(self,text,x,y,w=700):
        self.text(text,x,y,w,size=17,bold=True,color=C['muted'])


pages=[]
def new(key):
    p=Page(key); pages.append(p);return p


# 00 - navigation: each tile is an internal page link.
p=new('map')
p.text('Как читать файл',60,166,500,size=25,bold=True)
p.text('↗ открывает граф или пояснение. Номера карты и колонтитула - страницы PDF; вкладки draw.io имеют номера 00-42.',60,208,1630,size=18)
groups=[
    ('Графы и фокусы', [('overview','Обзор связей'),('r1','Граф R1'),('r2','Граф R2'),('aservice','Граф A-SERVICE'),('rin','Граф выходной R-IN'),('ratt','Цель «не требуется»'),('boundaries','Границы графов'),('workscopes','Соединить рабочие графы'),('originrecord','Запись происхождения')]),
    ('Оценка и сведения', [('canon','Смешанный канон'),('negative','Отрицательный канон'),('compare','Сопоставление / QRPE'),('canonmodes','Смысл условий канона'),('canonpattern','Самодостаточный канон'),('patternmatch','Реальные зависимости'),('awaive','Проверка необходимости'),('anotify','Action на бумаге'),('rnotify','Исключение способов'),('materials','Информация / Evidence'),('strength','Жёсткий и мягкий довод')]),
    ('Работа и линзы', [('closure','Закрытие / блокировки'),('plan','Plan во времени'),('history','История / identity'),('lens','Базовая линза'),('workflow','Графы целей работы'),('catalog','Каталог линз'),('factswork','Факты и основания работы'),('historygoal','Свой граф истории'),('evidencegoal','Свой граф Evidence'),('truth','Истинность / переоткрытие'),('stalechain','Пересмотр цепочки stale')]),
    ('Построение графа', [('retention','Критерии C1/C2/C3'),('drawchoice','Наносить / не наносить'),('adraw','Граф A-L-SAVE'),('rules','Граф R-L-SEM'),('amodel','Граф A-L-MODEL'),('wmethods','Рабочие Actions'),('aselect','Граф выбора линз'),('rolecheck','Правильные R и Actions'),('canoncheck','Каноны и QRPE'),('linkrules','Связи, состояния, типы'),('decompose','Подробность и разбиение R')]),
]


for col,(title,links) in enumerate(groups):
    x=60+col*425
    p.panel(x,278,405,500,title)
    for row,(dest,label) in enumerate(links):
        page_no=[q[0] for q in PAGES].index(dest)+1
        p.nav(f'{page_no:02d}  {label}  ↗',dest,x+18,332+row*40,369,34)
p.panel(60,786,1680,280,'Обозначения')
legend=[('R','Requirement','Что должно быть истинным'),('A','Action','Конкретный способ'),('Context','Context','Значимые факты / обстоятельства'),('Canon','Граф канона','С чем сопоставлять'),('Info','Информация','Пояснение / теория'),('Evidence','Evidence','Подтверждение утверждения')]
for i,(kind,title,body) in enumerate(legend):
    x=82+(i%3)*552;y=842+(i//3)*96
    fill,stroke=C[kind]
    p.shape(x,y+2,38,38,fill,stroke,kind='ellipse' if kind=='A' else 'round')
    p.text(title,x+54,y,450,size=18,bold=True)
    p.text(body,x+54,y+27,450,size=16,color=C['muted'])
p.text('Сплошная связь: реализация / принятое происхождение. Пунктир: влияние, пояснение или потенциальная связь на бумаге.',82,1032,1610,size=15,color=C['muted'])
p.text('Граф R заканчивается на Actions или под-R; граф A - на своих выходных R; граф канона - на проверяемом A.',65,1082,1670,size=15,bold=True,color=C['purple'])


# 01 - a view is not an owner of its displayed entities.
p=new('overview')
p.node('R0',690,163,420,150)
p.node('R1',250,393,370,155)
p.node('R2',1180,393,370,155)
p.edge('R0','R1',via=[(900,350),(435,350)],label='Прямая подцель R → R',lx=295,ly=331,lw=260)
p.edge('R0','R2',via=[(900,350),(1365,350)],label='Прямая подцель R → R',lx=1210,ly=331,lw=260)
p.node('A-SERVICE',790,622,220)
p.edge('R1','A-SERVICE',via=[(435,590),(900,590)],label='Способ для R1',lx=430,ly=567,lw=170)
p.edge('R2','A-SERVICE',via=[(1365,590),(900,590)],label='Тот же способ для R2',lx=1160,ly=567,lw=240)
p.note('Не два похожих Action', 'A-SERVICE - один экземпляр. Выбор, состояние и история общие во всех его графах.',70,650,570,150,color=C['blue'])
p.note('Не закрытие двух целей', 'Выбор общего A не означает, что R1 и R2 достигнуты. Их результаты проверяются отдельно.',1160,650,570,150,color=C['blue'])
p.panel(65,890,1670,176,'Другие фокусы этого же примера')
p.nav('Свой граф Action ↗','aservice',90,946,390,50)
p.nav('Канон и реальные блоки ↗','compare',520,946,390,50)
p.nav('Обязательные выходы ↗','closure',950,946,350,50)
p.nav('История и identity ↗','history',1340,946,370,50)


# 02 - R1 offers Actions; their output requirements live in their Action graphs.
p=new('r1')
p.node('R0',80,176,355,145)
p.node('R1',712,340,380,160)
p.edge('R0','R1',s='right',via=[(600,248),(600,420)],t='left',label='Непосредственный родитель',lx=450,ly=224,lw=282)
p.node('A-SERVICE',412,646,214)
p.node('A-MANUAL',1132,646,214)
p.edge('R1','A-SERVICE',via=[(902,568),(519,568)],label='Выбранный способ',lx=570,ly=535,lw=230)
p.edge('R1','A-MANUAL',via=[(902,568),(1239,568)],dashed=True,label='Другой кандидат',lx=1120,ly=544,lw=200)
p.note('Общий экземпляр Action', 'A-SERVICE служит также R2. Его ситуация и выходные требования видны в собственном графе. Для оценки отдельно открываются примеры канонов.',65,407,490,158,link='aservice')
p.note('Возможен пересмотр исходных целей', 'Другой способ может показать ценность более простого решения. Существенные основания сохраняются при отдельном пересмотре целей и связей.',1110,176,595,150,color=C['QRPE'][1])
p.panel(65,919,1670,167,'Следующий переход: собственный граф Action')
p.nav('A-SERVICE: оценка и выходные R ↗','aservice',90,978,790,53)
p.nav('Как разделены R / A / канон ↗','boundaries',920,978,790,53)


# 03 - graph of R2: four compatible methods, with links to their own graphs.
p=new('r2')
p.node('R0',65,174,345,150)
p.node('R2',710,337,380,155)
p.edge('R0','R2',s='right',t='left',via=[(590,249),(590,414)],label='Прямая подцель',lx=434,ly=223,lw=190)
p.section('Четыре способа могут дополнять друг друга; выбран A-SERVICE.',65,526,1650)
for x,a in zip([155,565,975,1385],['A-SERVICE','A-HISTORY','A-NOTIFY','A-GUIDE']):
    p.node(a,x,620,220)
    p.edge('R2',a,via=[(900,583),(x+110,583)],dashed=E[a].candidate)
p.node('I-ARCH',1205,172,470,150)
p.edge('I-ARCH','R2',s='bottom',t='right',via=[(1440,414)],dashed=True,color=C['Info'][1],label='Поясняет термин «статус»',lx=1210,ly=365,lw=280)
p.panel(65,919,1670,167,'Выходы способов открываются в их графах Action')
p.nav('Общий A-SERVICE ↗','aservice',90,979,790,53)
p.nav('Ещё не выбранный A-NOTIFY ↗','anotify',920,979,790,53)


# 04 - the central action view: literal facts and canon references side by side.
p=new('aservice')
p.section('РЕАЛИЗУЕМЫЕ ЦЕЛИ',65,158,650)
p.node('R1',65,193,342,150)
p.node('R2',443,193,342,150)
p.section('ОТКРЫТЫЕ ПРИМЕРЫ ДЛЯ СРАВНЕНИЯ',1040,158,650)
p.node('CAN-SERVICE',1025,193,337,150)
p.node('CAN-EXTERNAL',1395,193,337,150)
p.node('A-SERVICE',791,487,218)
p.edge('R1','A-SERVICE',via=[(236,383),(835,383)],t=(.2,.1),label='Реализует R1',lx=390,ly=360,lw=176)
p.edge('R2','A-SERVICE',via=[(614,414),(878,414)],t=(.4,.02),label='Реализует R2',lx=617,ly=390,lw=176)
p.text('Открытие примера не создаёт зависимости рабочего A от канона.',1040,352,690,size=14,color=C['purple'])
p.node('C-TEAM',65,415,345,150)
p.node('C-OPS',65,625,345,150)
p.node('R-PRIV',1389,385,345,150)
p.node('R-OFFLINE',1389,565,345,150)
p.node('C-HOST',1389,725,345,155)
p.edge('C-TEAM','A-SERVICE',s='right',t='left',via=[(567,490),(567,596)],dashed=True,color=C['good'],label='+ Фактическая поддержка',lx=428,ly=464,lw=285)
p.edge('C-OPS','A-SERVICE',s='right',t=(.12,.82),via=[(630,700),(630,666)],dashed=True,color=C['bad'],label='- Мягкий довод: soft',lx=427,ly=714,lw=320)
p.edge('R-PRIV','A-SERVICE',s='left',t='right',via=[(1243,460),(1243,596)],dashed=True,color=C['blue'],label='Ограничение защиты данных',lx=1040,ly=416,lw=320)
p.edge('R-OFFLINE','A-SERVICE',s='left',t=(.98,.55),via=[(1290,640),(1290,607)],dashed=True,color=C['blue'],label='Ограничение закрытой сети',lx=1052,ly=554,lw=300)
p.edge('C-HOST','A-SERVICE',s='left',t=(.88,.82),via=[(1190,802),(1190,666)],dashed=True,color=C['teal'],label='Факт для отрицательного канона',lx=1018,ly=734,lw=160)
p.nav('Сопоставление / QRPE ↗','compare',1040,812,315,41)
p.section('ВСЕ ВЫХОДЯЩИЕ R ОБЯЗАТЕЛЬНЫ ПРИ ВЫБОРЕ A',65,812,710)
p.text('R-ATT позднее обоснованно признана ненужной.',65,846,710,size=15,color=C['muted'])
outs=[('R-IN',65,335),('R-TRACK',458,360),('R-SEC',884,360),('R-ATT',1310,425)]
for ent,x,w in outs:
    p.node(ent,x,923,w,172)
    p.edge('A-SERVICE',ent,s=(.5,1),t='top',via=[(900,889),(x+w/2,889)],color=C['blue'])
p.label('Подцель R1',78,884,180,color=C['blue'])
p.label('Подцель R2',469,884,180,color=C['blue'])
p.label('Корректность A',895,884,220,color=C['blue'])
p.label('Подцель R1 и R2',1320,884,240,color=C['blue'])


# 05 - canonical conditions refer to the very same assessed A-SERVICE.
p=new('canon')
positive=p.panel(60,166,1100,610,'Положительная каноническая ситуация: AND',fill='#FCFAFF',color=C['purple'])
p.custom('K-R-REGISTER','R','Заявки должны учитываться без потерь',90,233,430,170,state='Каноническая R',canonical=True)
p.custom('K-R-STATUS','R','Заявителю должен быть понятен статус',560,233,535,170,state='Каноническая R',canonical=True)
p.panel(90,429,1038,300,'OR: достаточно одного; оба тоже допустимы',fill='#FFFFFF',color=C['teal'])
p.custom('K-C-TEAM','Context','Есть команда, способная развивать сервис',120,491,460,175,state='Канонический контекст',canonical=True)
p.custom('K-C-READY','Context','Есть пригодная готовая платформа',625,491,470,175,state='Канонический контекст',canonical=True)
p.node('A-SERVICE',1267,532,228,home='canon')
p.edge(positive,'A-SERVICE',s='right',t='left',via=[(1214,471),(1214,646)],color=C['good'])
p.label('+ Вся AND-ситуация',1218,446,500,color=C['good'])
negative=p.panel(60,819,1100,240,'Мягкие доводы: OR; сила soft у каждого',fill='#FFF9FA',color=C['bad'])
p.custom('K-C-OPS','Context','Нет владельца эксплуатации',90,878,470,155,state='Soft: риск эксплуатации',canonical=True)
p.custom('K-R-PRIV','R','Персональные данные должны быть защищены',605,878,525,155,state='Soft: риск раскрытия, не факт нарушения',canonical=True)
p.edge(negative,'A-SERVICE',s='right',t='bottom',via=[(1177,939),(1177,795),(1381,795)],dashed=True,color=C['bad'])
p.text('Soft относится к доводу о риске. Защита данных остаётся обязательной R; нарушение проверяется отдельно.',85,1036,1050,size=13,color=C['bad'])
p.note('Текущая проверка', 'Здесь показан тот же проверяемый A-SERVICE. Его показ задаёт текущая проверка; внешний ref на рабочий Action внутри канона не хранится.',1207,184,523,205,color=C['purple'])
p.note('Условия - показательные', 'R и контексты здесь описывают ситуации, с которыми сравнивают реальность. Это не ссылки на рабочие инстансы. Результат проверки и реальные зависимости находятся на рабочей стороне.',1207,844,523,214,color=C['purple'])


# 06 - absence of the negative match rests on tested method capability.
p=new('negative')
negative=p.panel(65,172,1090,526,'Жёсткая несовместимость: hard, вся AND-группа',fill='#FFF9FA',color=C['bad'])
p.custom('K-R-CLOSED','R','Работа идёт только в закрытой сети',100,250,445,170,state='Каноническая R',canonical=True)
p.custom('K-C-EXTERNAL','Context','Способ обязательно обращается во внешнюю сеть',635,250,470,170,state='Канонический контекст',canonical=True)
p.label('Hard срабатывает, только если подтверждена вся AND-группа',195,482,830,color=C['bad'],size=20,fill='#FFF0F2')
p.node('A-SERVICE',1270,377,240,home='negative')
p.edge(negative,'A-SERVICE',s='right',t='left',via=[(1213,435),(1213,497)],dashed=True,color=C['bad'])
p.panel(65,746,1668,322,'Пример применения AND, без ссылок на рабочие инстансы')
p.note('Оба условия установлены', 'Нужна работа только в закрытой сети, а A обязательно обращается наружу. Полное hard-условие подтверждено: A исключается; плюсы его не компенсируют.',95,813,475,205,color=C['bad'])
p.note('Второе условие не совпало', 'Способ проверенно работает внутри закрытой сети: одного первого условия недостаточно для этого AND-довода.',610,813,505,205,color=C['teal'])
p.note('Возможность неизвестна', 'Наличие хостинга само по себе не доказывает автономную работу способа. Нужна проверка; неизвестное остаётся неизвестным.',1155,813,545,205,color=C['purple'])
p.note('Action текущей проверки', 'Показан проверяемый A-SERVICE. Сам канон содержит только локальные условия; внешний ref на этот A не хранится.',1197,173,536,153,color=C['purple'])


# 07 - explicit traceability, with no stronger R inferred from a weaker one.
p=new('compare')
cols=[70,490,930,1280]
head=['Условие канона','Реальные сущности','Оценка','Основание / следствие']
cw=[380,400,310,450]
for x,w,title in zip(cols,cw,head):
    p.shape(x,166,w,48,'#E8EDF6',None,kind='round')
    p.text(title,x+15,178,w-30,size=18,bold=True)
rows=[
    ('K-R-REGISTER\nCAN-SERVICE v1','R1 v1\nРегистрация без потерь','Совпало / +','A реализует R1.\nЕдиный учёт из R1 не выводится.',C['blue']),
    ('K-R-STATUS\nCAN-SERVICE v1','R2 v1\nПонятный статус','Совпало / +','Тот же A реализует R2.\nОбщий экземпляр.',C['blue']),
    ('K-C-TEAM OR K-C-READY','C-TEAM v1\nКоманда есть; платформа неизвестна','OR выполнено / +','Одного условия достаточно.\nВторое тоже может совпасть.',C['teal']),
    ('K-C-OPS\nCAN-SERVICE v1','C-OPS v1\nНет владельца эксплуатации','Совпало / soft','F-OPS: открытый риск;\nоснование выбора сохранено.',C['bad']),
    ('K-R-PRIV\nCAN-SERVICE v1','R-PRIV v1\nЗащита персональных данных','Применимо / soft','Риск раскрытия, не доказанное\nнарушение. R-SEC задаёт защиту.',C['bad']),
    ('K-R-CLOSED AND K-C-EXTERNAL','R-OFFLINE v1 + C-HOST v1\nПроверена работа в закрытой сети','Hard: AND не совпало','Внешний сервис не обязателен\nдля этого A в проверенном объёме.',C['purple']),
]
for i,(a,b,c,d,color) in enumerate(rows):
    y=231+i*103
    p.shape(65,y,1670,94,'#FFFFFF',C['border'],kind='round')
    for x,w,txt in zip(cols,cw,[a,b,c,d]):
        p.text(txt,x+14,y+15,w-28,size=16,color=color if x==cols[2] else C['ink'])
p.note('QRPE / Finding до выбора', 'F-OPS появился при оценке кандидата. В учебном выборе сохранено объяснение допустимости этого риска. Сам Finding не создаёт скрытого обязательства назначить владельца.',65,878,810,200,color=C['QRPE'][1])
p.note('Неизвестные и новые обязательства', 'Неизвестное помечается явно. Если из оценки следует новое обязательство, его принимают явной R и связью, а не оставляют обещанием в пояснении.',915,878,820,200,color=C['purple'])


# 08 - completed output with explicit provenance and evidence, not vacuous completion.
p=new('rin')
p.node('R1',100,175,380,153)
p.node('A-SERVICE',1210,170,215)
p.node('R-IN',690,460,430,170)
p.edge('R1','R-IN',via=[(290,394),(905,394)],label='Через A: подцель только R1',lx=365,ly=368,lw=380)
p.edge('A-SERVICE','R-IN',s='bottom',t='right',via=[(1317,545)],label='Ввёл обязательную R',lx=1180,ly=416,lw=320)
p.node('E-REG',92,737,510,171)
p.edge('E-REG','R-IN',s='right',t='left',via=[(640,822),(640,545)],dashed=True,color=C['good'],label='Подтверждает результат v1',lx=620,ly=704,lw=340)
p.note('Результат учебного примера', 'В учебной проверке заявка восстановлена после перезапуска. Область подтверждения указана в E-REG; закрытие R-IN зафиксировано отдельно.',991,744,735,169,color=C['good'])
p.note('Состояние родителей / точная запись происхождения ↗', 'A-SERVICE остаётся открыт: R-TRACK и R-SEC ещё открыты. R1 также не закрывается автоматически от закрытия R-IN.',92,962,1634,106,color=C['blue'],link='originrecord')
p.label('Лист без подцелей ≠ выполненная цель',974,667,740,color=C['bad'],size=18)


# 09 - an accepted wrapper/outcome later explicitly found unnecessary.
p=new('ratt')
p.node('R1',65,171,350,150)
p.node('R2',472,171,350,150)
p.node('A-SERVICE',1325,174,210)
p.node('R-ATT',680,480,435,172)
p.edge('R1','R-ATT',via=[(240,405),(800,405)],t=(.28,0),label='Подцель R1',lx=310,ly=377,lw=190)
p.edge('R2','R-ATT',via=[(647,441),(900,441)],t='top',label='Подцель R2',lx=633,ly=409,lw=190)
p.edge('A-SERVICE','R-ATT',t='right',via=[(1430,566)],label='Принята вместе с A',lx=1215,ly=412,lw=290)
p.node('A-NEED',786,788,222)
p.edge('R-ATT','A-NEED',label='Явный Action пересмотра',lx=920,ly=702,lw=320)
p.note('До пересмотра', 'R-ATT была принята как обязательная. Нельзя было просто не выбрать эту выходную R при выборе A-SERVICE.',65,633,505,178,color=C['blue'])
p.note('После принятого и закрытого A-NEED', 'В учебном примере необходимость отвергнута с основаниями и Evidence. Исход R-ATT: «не требуется», а не «реализована».',1190,633,545,210,color='#718096')
p.note('Что снято', 'Блокировка этой R снята. R1/R2 и A-SERVICE сами от этого не закрываются и не становятся ненужными.',65,929,595,140,color=C['blue'])
p.note('Если R ещё нужна другому родителю', 'Одна локальная оценка не отменяет чужие требования. До общего исхода проверяется весь действующий объём использования.',1135,929,600,140,color=C['bad'])


# 10 - necessity is investigated without a predetermined conclusion.
p=new('awaive')
p.node('R-ATT',670,169,460,171)
needcanon=p.panel(65,386,510,420,'CAN-NEED: канонические условия',fill='#FCFAFF',color=C['purple'])
p.custom('K-C-NEED','Context','Необходимость выходной цели требует проверки',94,453,450,160,state='Канонический контекст',canonical=True)
p.custom('K-R-OTHERS','R','Исходные цели должны сохранить смысл и достаточность',94,640,450,150,state='Каноническая R',canonical=True)
p.node('A-NEED',790,484,220)
p.node('R1',65,177,280,165)
p.node('R2',370,177,280,165)
p.node('C-NEED-BEFORE',1230,386,505,170)
p.node('E-ATT',1230,604,505,150)
p.edge('R-ATT','A-NEED',label='Проверить необходимость',lx=925,ly=381,lw=300)
p.edge('R1','A-NEED',s='bottom',t=(.13,.16),via=[(205,350),(725,350),(725,519)],dashed=True,color=C['blue'])
p.edge('R2','A-NEED',s='bottom',t=(.22,.08),via=[(510,367),(751,367),(751,501)],dashed=True,color=C['blue'])
p.edge('C-NEED-BEFORE','A-NEED',s='left',t=(.95,.3),via=[(1130,471),(1130,550)],dashed=True,color=C['teal'])
p.edge('A-NEED','E-ATT',s=(.95,.7),t='left',via=[(1130,638),(1130,679)],dashed=True,color=C['good'])
p.label('Результат проверки / t4',1190,781,540,color=C['good'],size=18)
p.text('Синие связи: R1/R2 влияют - сохраняем достаточность остальных целей.',68,814,900,size=15,color=C['blue'])
p.note('Отдельный исход R-ATT', 'В этом эпизоде проверка дала результат «не требуется». Если потребность подтверждается, R остаётся обязательной и для неё выбирают реализацию.',65,850,530,225,color='#718096')
p.note('Что подтверждено', 'Исследованы потребности R1/R2 и все использования цели. E-ATT относится к согласованному объёму v1; отсутствие файлов сейчас само по себе не доказывает их ненужность. Action проверки выбран и отдельно закрыт.',641,850,1094,225,color=C['good'])


# 11 - candidate own action graph, no acceptance of its hypothetical child.
p=new('anotify')
p.node('R2',665,166,465,166)
p.node('A-NOTIFY',790,482,220)
p.edge('R2','A-NOTIFY',dashed=True,label='Пока возможный способ',lx=930,ly=382,lw=300)
p.panel(65,378,545,402,'CAN-NOTIFY: каноническая ситуация',fill='#FCFAFF',color=C['purple'])
p.custom('K-R-CHANGE','R','Заявителю должен быть понятен текущий статус',95,446,485,160,state='Каноническая R',canonical=True)
p.custom('K-C-CHANNEL','Context','Доступен надёжный канал связи',95,630,485,128,state='Канонический контекст',canonical=True)
p.node('C-CONTACT',1210,385,525,164)
p.node('F-CHANNEL',1210,608,525,164)
p.edge('C-CONTACT','A-NOTIFY',s='left',t='right',via=[(1130,467),(1130,592)],dashed=True,color=C['teal'],label='Ещё не уточнено',lx=1082,ly=551,lw=220)
p.edge('A-NOTIFY','F-CHANNEL',s=(.85,.85),t='left',via=[(1140,670),(1140,690)],dashed=True,color=C['QRPE'][1])
p.node('R-NOTIF',668,891,465,167)
p.edge('A-NOTIFY','R-NOTIF',dashed=True,label='При выборе A станет обязательной',lx=934,ly=798,lw=410)
p.note('Сейчас: только бумага', 'R-NOTIF не принята; нет выполнения или закрытия. Findings допустимы уже при оценке кандидата.',65,880,530,178,color=C['blue'])
p.note('Переход в граф R', 'Выбор конкретного канала происходит внутри R-NOTIF. Это не выбор, принимать ли эту выходную цель.',1210,880,525,178,color=C['blue'],link='rnotify')


# 12 - explicit exclusive action group inside a mandatory-if-chosen child R.
p=new('rnotify')
p.node('R2',65,169,355,150)
p.node('A-NOTIFY',1310,166,211)
p.node('R-NOTIF',666,420,465,170)
p.edge('R2','R-NOTIF',via=[(242,365),(800,365)],t=(.3,0),dashed=True,label='Потенциальная подцель R2',lx=310,ly=333,lw=365)
p.edge('A-NOTIFY','R-NOTIF',via=[(1415,505)],t='right',dashed=True,label='Потенциальный ввод через A',lx=1198,ly=393,lw=340)
p.panel(375,663,1050,390,'Явная группа: основной канал этой версии - выбрать один',fill='#FFFDF7',color=C['A'][1],dashed=True)
p.node('A-EMAIL',505,755,220)
p.node('A-MSG',1075,755,220)
p.edge('R-NOTIF','A-EMAIL',via=[(898,636),(615,636)],dashed=True)
p.edge('R-NOTIF','A-MSG',via=[(898,636),(1185,636)],dashed=True)
p.label('Нельзя выбрать оба в этой группе',693,978,430,color=C['A'][1],size=17,fill='#FFFDF7')
p.note('Это не глобальный XOR', 'Группа относится только к этим двум способам и указанному объёму. У R2 четыре способа могут дополнять друг друга.',65,704,275,347,color=C['blue'],link='r2')
p.note('Необязательного выхода нет', 'Если выбран A-NOTIFY, принимается R-NOTIF. Дальше её граф определяет способ. В примере исходный A ещё кандидат.',1460,704,275,347,color=C['blue'])


# 13 - shared material, references and claim-bearing evidence.
p=new('materials')
p.panel(65,170,790,430,'Информационный объект')
p.node('I-ARCH',95,235,729,157)
p.text('Содержимое: термины, теория, пояснение архитектуры.\nСсылка на файл: docs/example/service-overview.md (пример пути).\nМожет пояснять R, A, Context и другие нужные элементы. Сам канон не получает внешних ссылок на рабочие инстансы.',98,423,720,size=18,color=C['muted'])
p.panel(905,170,830,430,'Evidence')
p.node('E-REG',935,235,769,157)
p.text('Утверждение: заявка сохраняется после перезапуска.\nОбласть: сценарий v1; источник: отчёт проверки восстановления v1.\nЗафиксированы проверка, версия/содержимое и ограничения.',938,423,740,size=18,color=C['muted'])
p.node('R2',65,733,330,158)
p.node('A-SERVICE',485,711,208)
p.node('C-TEAM',800,733,340,158)
p.node('R-IN',1280,733,455,158)
p.edge('I-ARCH','R2',s='right',t='top',via=[(843,313),(843,662),(230,662)],dashed=True,color=C['Info'][1])
p.edge('I-ARCH','A-SERVICE',s='right',t='top',via=[(843,313),(843,662),(589,662)],dashed=True,color=C['Info'][1])
p.edge('I-ARCH','C-TEAM',s='right',t='top',via=[(843,313),(843,662),(970,662)],dashed=True,color=C['Info'][1])
p.edge('E-REG','R-IN',s='right',t='top',via=[(1718,313),(1718,670),(1507,670)],dashed=True,color=C['good'])
p.note('Наличие текста не создаёт другие роли', 'Пояснение само не становится целью, контекстом-фактом или доказательством. Evidence подтверждает указанное утверждение; один путь к файлу или SHA не доказывает его смысл.',65,959,1670,111,color=C['Info'][1])


# 14 - present blockers; hypothetical readiness kept visibly separate.
p=new('closure')
p.node('A-SERVICE',792,170,216)
p.label('ТЕКУЩИЙ СНИМОК: A ОТКРЫТ',1065,253,590,color=C['A'][1],size=21)
outs=[('R-IN',65,340),('R-TRACK',460,365),('R-SEC',885,365),('R-ATT',1310,425)]
for ent,x,w in outs:
    p.node(ent,x,487,w,178)
    p.edge('A-SERVICE',ent,via=[(900,432),(x+w/2,432)],color=C['blue'])
labels=[('Блокировка снята',C['good']),('БЛОКИРУЕТ',C['bad']),('БЛОКИРУЕТ',C['bad']),('Блокировка снята',C['muted'])]
for (ent,x,w),(txt,col) in zip(outs,labels):
    p.label(txt,x+5,676,w-10,color=col,size=19)
p.panel(65,788,1670,284,'Правило перехода - это не уже произошедшие события',fill='#FFFFFF')
steps=[('1. Нет открытых обязательных R','Проверяется весь актуальный объём и все использования.'),('2. Есть фактический результат','Готовность по зависимостям сама по себе не доказательство.'),('3. Отдельное закрытие A / R','Никакого автоматического закрытия родителя от дочернего блока.')]
for i,(title,body) in enumerate(steps):
    x=92+i*555
    p.text(title,x,855,510,size=19,bold=True)
    p.text(body,x,902,510,size=18,color=C['muted'])
p.text('«Не требуется» отличается от «достигнуто». Пустой список подцелей не равен выполнению. Новый объём не переписывает старые факты.',91,1020,1615,size=16,color=C['bad'])


# 15 - the temporal plan is a distinct view, with explicit prospective labels.
p=new('plan')
p.panel(65,169,545,845,'На бумаге',fill='#FCFDFF',color=C['blue'])
p.node('A-NOTIFY',223,261,220)
p.node('R-NOTIF',110,575,455,166)
p.edge('A-NOTIFY','R-NOTIF',dashed=True,color=C['blue'])
p.text('Кандидат и потенциальная R.\nНет принятия, временного места,\nвыполнения или закрытия.',100,808,460,size=19,color=C['muted'])
p.panel(660,169,1075,845,'Plan: временное представление той же работы')
p.text('Условная шкала примера. Это намерения и размещение, а не отчёт о выполнении.',690,228,1005,size=18,color=C['muted'])
for i,(label,y) in enumerate([('СЛОТ 1',321),('СЛОТ 2',512),('СЛОТ 3',703)]):
    p.text(label,690,y+26,145,size=15,bold=True,color=C['muted'])
    p.shape(865,y,818,137,'#FFFFFF',C['border'],kind='round')
    if i==0:
        title='A-SERVICE / реализация сервиса';body='Ссылка на тот же экземпляр, который служит R1 и R2.'
    elif i==1:
        title='R-SEC / проверка доступа';body='Размещена работа над ещё открытой обязательной R.'
    else:
        title='A-SERVICE / проверка готовности';body='Другая запись Plan с тем же ref. Не новое исполнение A.'
    p.text(title,892,y+20,759,size=21,bold=True)
    p.text(body,892,y+65,759,size=18,color=C['muted'])
p.note('Разные состояния', 'Нарисован ≠ выбран ≠ размещён в Plan ≠ выполнен ≠ закрыт. Время задаётся явно в Plan; граф целей сам его не создаёт.',690,884,994,116,color=C['blue'])
p.nav('История фактов и повторное выполнение ↗','history',65,1040,1668,46)


# 16 - one identity and a real sequence, not histories cloned per view.
p=new('history')
p.panel(65,168,1030,892,'Учебная история A-SERVICE и его целей')
history=[
    ('t0 / Нарисован кандидат','Созданы связи R1/R2 и потенциальные выходные R.'),
    ('t1 / Проведена оценка','Сопоставлены каноны и факты; появился открытый F-OPS.'),
    ('t2 / Выбран A-SERVICE','Все R-IN / R-TRACK / R-SEC / R-ATT приняты как обязательные.'),
    ('t3 / Закрыта R-IN','Отдельный факт по E-REG. Родители сами не закрылись.'),
    ('t4 / Принят и закрыт A-NEED','Проверена ненужность R-ATT; основание и E-ATT сохранены.'),
    ('t5 / R-ATT: не требуется','Старое принятие осталось в истории. A-SERVICE ещё открыт.'),
]
for i,(title,body) in enumerate(history):
    y=237+i*129
    p.shape(90,y,977,112,'#F7F9FD',C['border'],kind='round')
    p.text(title,112,y+15,932,size=20,bold=True)
    p.text(body,112,y+53,932,size=17,color=C['muted'])
p.note('Одна identity', 'A-SERVICE в графах R1, R2, своём графе и Plan - один рабочий экземпляр. Повторный показ не создаёт выбор или выполнение.',1135,170,600,201,color=C['blue'])
p.note('Рабочие графы', 'Один scope: приложение или пересекающиеся приложения. Общая работа соединяет графы. Для независимой дальнейшей работы допустимы самостоятельные экземпляры.',1135,414,600,156,color=C['purple'])
p.nav('Общая / независимая работа ↗','workscopes',1135,582,600,37)
p.note('Повторное выполнение', 'При изменении плана или потере результата можно вернуться к тому же A. Ложная в своей области R открывается снова. Прежние факты остаются в истории.',1135,648,600,191,color=C['A'][1])
p.note('Основания в момент решения', 'История хранит действовавшие версии и факты. Текущая картинка не доказывает, что такие связи существовали в прошлом.',1135,882,600,178,color=C['Info'][1])


# 17 - a real work goal and its direct subgoals; no invented storage modes.
p=new('lens')
p.node('R-LENS',640,170,520,165)
p.section('ПОДЦЕЛИ ВЕДЕНИЯ РАБОТЫ ЧЕРЕЗ ГРАФЫ',65,426,1600)
children=[('R-L-CONTEXT',65),('R-L-OPTIONS',490),('R-L-PAPER',915),('R-L-FACTS',1340)]
for entity,x in children:
    p.node(entity,x,545,395,175)
    p.edge('R-LENS',entity,via=[(900,479),(x+197.5,479)],color=C['blue'])
p.panel(65,794,1670,278,'Собственные графы раскрывают, как исполнять эти требования')
p.nav('Контекст и варианты ↗','workflow',92,855,487,48)
p.nav('Наносить / не наносить ↗','drawchoice',622,855,487,48)
p.nav('Факты и основания работы ↗','factswork',1152,855,555,48)
p.text('Выбор «сохранять» означает нанесение конкретного фрагмента на бумагу. После выбора A-L-SAVE его требования к построению обязательны.',95,949,1600,size=19)
p.text('Нанесённый граф может храниться, пересматриваться и описывать будущую работу; изображение способа не исполняет его.',95,1022,1600,size=17,color=C['muted'])


# 18 - the same assessed A-L-SAVE, with C1/C2/C3 as canonical contexts.
p=new('retention')
keep=p.panel(65,171,1165,672,'AND: выполняется C3 и хотя бы одно из C1/C2',fill='#FCFAFF',color=C['purple'])
p.panel(95,241,1104,305,'OR: C1 или C2; оба вместе допустимы',fill='#FFFFFF',color=C['teal'])
p.custom('C1 / K-DECISION','Context','Есть содержательное решение и основания для него',125,309,500,184,state='Условие канона',canonical=True)
p.custom('C2 / K-DECOMPOSITION','Context','Есть ценная декомпозиция задачи',660,309,507,184,state='Условие канона',canonical=True)
p.custom('C3 / K-FUTURE-VALUE','Context','Будущая ценность сохранения оправдывает затраты',125,594,1042,194,state='Хранение, поддержка и возможное повторное выполнение работы',canonical=True)
p.node('A-L-SAVE',1368,387,240,home='retention')
p.edge(keep,'A-L-SAVE',s='right',t='left',color=C['purple'])
p.note('Текущая проверка', 'Показан проверяемый A-L-SAVE без сохранённой внешней ссылки из канона. C1/C2/C3 - самодостаточные условия-примеры; реальные основания находятся на рабочей стороне.',1280,747,455,309,color=C['purple'])
p.panel(65,886,1165,172,'Проверка формулы на двух учебных ситуациях')
p.text('C1 = да, C2 = да, C3 = да  →  критерий выполнен.\nC1 = да, C2 = нет, C3 = нет  →  критерий не выполнен.',94,944,1090,size=21,bold=True)
p.text('Нанесение на бумагу не выбирает изображённые способы к исполнению и не размещает их во временном Plan.',65,1081,1640,size=16,color=C['muted'])


# 19 - keep/no-keep is a local drawing choice, not a mode for an entire model.
p=new('drawchoice')
p.node('R-LENS',65,174,445,165)
p.node('R-L-PAPER',680,376,450,174)
p.edge('R-LENS','R-L-PAPER',s='right',t='left',via=[(590,256),(590,463)],label='Прямая подцель линзы',lx=538,ly=291,lw=300)
p.panel(380,601,1070,312,fill='#FFFDF8',color=C['A'][1],dashed=True)
p.text('Один фрагмент: выбрать одно действие',700,616,640,size=18,bold=True,color=C['A'][1],align='center')
p.node('A-L-SAVE',425,672,220)
p.node('A-L-SKIP',1175,672,220)
p.edge('R-L-PAPER','A-L-SAVE',via=[(905,578),(535,578)],color=C['blue'])
p.edge('R-L-PAPER','A-L-SKIP',via=[(905,578),(1285,578)],dashed=True,color=C['line'])
p.note('Единица выбора', 'Решение относится к конкретному содержательному решению или разбиению. «Не наносить» означает не создавать его блоки на бумаге вообще.',1195,174,540,180,color=C['purple'])
p.nav('Канон C1/C2/C3 ↗','retention',1195,385,540,47)
p.nav('Сопоставление в графе Action ↗','adraw',1195,451,540,47)
p.note('Переход к выходным требованиям', 'A-L-SAVE открывает собственный граф: там сопоставление с C1/C2/C3 и обязательная R-L-SEM. Здесь у R-L-PAPER показаны варианты действий.',65,955,1670,151,color=C['blue'],link='adraw')


# 20 - actual conditions are individual context blocks adjacent to the canon ref.
p=new('adraw')
p.node('R-L-PAPER',670,175,460,165)
p.node('CAN-KEEP',65,396,470,173)
p.node('A-L-SAVE',785,490,230)
p.node('C-L-C1',1220,175,515,180)
p.node('C-L-C2',1220,407,515,180)
p.node('C-L-C3',1220,639,515,180)
p.edge('R-L-PAPER','A-L-SAVE',label='Реализует требование к составу графа',lx=820,ly=399,lw=270)
p.text('Пример для сравнения; не зависимость рабочего A.',65,581,570,size=16,color=C['purple'])
p.edge('C-L-C1','A-L-SAVE',s='left',t=(.95,.3),via=[(1160,265),(1160,559)],dashed=True,color=C['good'])
p.edge('C-L-C2','A-L-SAVE',s='left',t='right',via=[(1135,497),(1135,605)],dashed=True,color=C['good'])
p.edge('C-L-C3','A-L-SAVE',s='left',t=(.9,.8),via=[(1120,729),(1120,674)],dashed=True,color=C['good'])
p.label('C1: да',1020,522,95,color=C['good'])
p.label('C2: да',1020,565,95,color=C['good'])
p.label('C3: да',1020,689,95,color=C['good'])
p.note('Что делает этот Action', 'A-L-SAVE наносит описание фрагмента на бумагу. Цели и способы внутри описания получают собственные состояния; изображение будущего действия не выполняет его.',65,647,570,185,color=C['blue'])
p.node('R-L-SEM',670,933,460,167)
p.edge('A-L-SAVE','R-L-SEM',label='Обязательный выход выбранного A',lx=930,ly=847,lw=310,color=C['blue'])
p.note('Область проверки', 'C1/C2/C3 относятся именно к этому фрагменту. Ценность повторного применения сопоставлена с затратами на хранение, поддержку и повторную работу.',1195,907,540,193,color=C['purple'])


# 21 - constructing a fragment has genuine required results and shared explanation.
p=new('rules')
p.node('A-L-SAVE',70,175,210)
p.node('R-L-PAPER',350,175,420,165)
p.node('R-L-SEM',755,420,420,165)
p.node('I-L-RULES',1245,175,490,160)
p.edge('A-L-SAVE','R-L-SEM',via=[(175,397),(710,397),(710,505)],t='left',color=C['blue'])
p.edge('R-L-PAPER','R-L-SEM',via=[(560,370),(965,370)],color=C['blue'])
p.edge('I-L-RULES','R-L-SEM',s='left',t='right',via=[(1225,255),(1225,505)],dashed=True,color=C['Info'][1])
p.panel(1245,380,490,354,'Смысл типов',fill='#FFFFFF',color=C['Info'][1])
p.text('R - что должно стать или быть истинным.\nA - конкретный способ или действие.\nContext - фактическое состояние или обстоятельство.\nКанон - что сравнивать с реальностью.\nИнформация - текст, теория, ссылка.\nEvidence - подтверждение указанного утверждения с областью и версией.',1268,435,444,size=17,color=C['muted'])
p.note('Модули: разрешённый набор', 'Базовый модуль очерчивает типы. Подключённый модуль может добавлять типы и код для Graph, Plan и истории. Механизм модулей остаётся в разработке; произвольные типы не вводятся.',65,451,590,181,color=C['Info'][1])
p.node('A-L-MODEL',400,655,200)
p.edge('R-L-SEM','A-L-MODEL',via=[(965,642),(500,642)],label='Способ построения и проверки',lx=664,ly=665,lw=500)
p.note('Собственный граф способа', 'Шесть обязательных требований построения раскрываются в графе A-L-MODEL: смысл R/A, каноны, QRPE, связи, состояния и доступные типы. Здесь у R-L-SEM показан сам способ.',65,944,1670,162,color=C['blue'],link='amodel')


# 22 - two real workflow goals; candidate outputs stay on paper.
p=new('workflow')
p.panel(65,174,810,930,'Собственный граф R-L-CONTEXT')
p.panel(925,174,810,930,'Собственный граф R-L-OPTIONS')
parent=p.node('R-LENS',100,235,740,160)
focus=p.node('R-L-CONTEXT',100,470,740,160)
p.edge(parent,focus,color=C['blue'])
p.text('До работы уточняются цель, достаточность результата, ограничения, факты, источники и неизвестные. Каталог линз просматривается перед работой.',100,654,440,size=17,color=C['muted'])
p.node('A-L-CLARIFY',590,850,200)
p.edge('R-L-CONTEXT','A-L-CLARIFY',s=(.8,1),via=[(692,811),(690,811)],dashed=True)
p.node('R-L-LENSES',105,885,395,170)
p.edge('R-L-CONTEXT','R-L-LENSES',s='left',via=[(80,550),(80,855),(302.5,855)],color=C['blue'])
p.label('Прямая под-R: открыть её граф',105,812,395,color=C['blue'])
p.nav('Граф этого Action ↗','wmethods',554,1061,285,34)
parent=p.node('R-LENS',960,235,740,160)
focus=p.node('R-L-OPTIONS',960,470,740,160)
p.edge(parent,focus,color=C['blue'])
p.text('Рассматриваются подходящие способы и существенные слабые альтернативы. Необычно ценный вариант может стать поводом явно пересмотреть исходные цели и контекст.',960,654,740,size=17,color=C['muted'])
p.node('A-L-EXPLORE',1220,850,220)
p.edge('R-L-OPTIONS','A-L-EXPLORE',s='right',via=[(1720,550),(1720,790),(1330,790)],dashed=True)
p.nav('Граф этого Action ↗','wmethods',1455,1020,245,45)


# 23 - catalogue is not the file's table of contents; it contains reusable lenses.
p=new('catalog')
p.panel(65,170,715,794,'Доступные графы линз: учебный каталог',color=C['Info'][1])
p.node('I-L-CATALOG',95,234,655,163)
p.nav('Базовая линза работы через RDG ↗','lens',95,438,655,59)
p.note('Линза проверки', 'Применимость: проверить реализацию и основания результатов. В каталоге хранится ссылка на её граф и версия.',95,530,655,145,color=C['Info'][1])
p.note('Линза передачи работы', 'Применимость: другой чат продолжает задачу. Цели: достаточный контекст, открытые вопросы и сохранённые основания.',95,709,655,145,color=C['Info'][1])
p.text('Записи условные: это пример устройства каталога, а не перечень установленных или принятых линз.',95,890,655,size=17,color=C['muted'])
p.node('R-L-CONTEXT',845,170,380,170)
p.node('R-L-LENSES',1280,170,455,170)
p.edge('R-L-CONTEXT','R-L-LENSES',s='right',t='left',color=C['blue'])

p.note('Прямое указание пользователя', 'Если пользователь назначил линзу, это требование учитывается при выборе. Его связь со способом видна в собственном графе A-L-SELECT.',933,381,740,154,color=C['blue'],link='aselect')
p.node('A-L-SELECT',1193,655,220)
p.edge('R-L-LENSES','A-L-SELECT',s='right',t='right',via=[(1757,255),(1757,765)],dashed=True,label='Найти применимые инструкции',lx=1412,ly=568,lw=300)
p.edge('I-L-CATALOG','A-L-SELECT',s='right',t='left',via=[(825,315),(825,765)],dashed=True,color=C['Info'][1])
p.nav('Открыть A-L-SELECT: требования и выход ↗','aselect',953,959,700,60)
p.text('Можно применять несколько подходящих линз. Их требования проверяются совместно; явное указание пользователя сохраняется.',65,1022,715,size=18,color=C['blue'])


# 24 - three focus types, not a single Requirement wave.
p=new('boundaries')
for x,title in [(60,'Собственный граф R1'),(640,'Граф A-SERVICE: фрагмент'),(1220,'Граф канона: фрагмент')]:
    p.panel(x,174,520,850,title)
r=p.node('R1',90,315,460,160)
a=p.node('A-SERVICE',210,594,220)
p.edge(r,a,color=C['blue'])
p.text('R показывает свой способ. По Action открывается его собственный граф.',90,845,460,size=18,color=C['muted'])
p.nav('Открыть граф R1 ↗','r1',90,949,460,45)
r1=p.node('R1',670,315,220,170)
r2=p.node('R2',920,315,220,170)
a=p.node('A-SERVICE',810,566,220)
o1=p.node('R-IN',670,836,220,180)
o2=p.node('R-SEC',920,836,220,180)
p.edge(r1,a,via=[(780,524),(920,524)],color=C['blue'])
p.edge(r2,a,via=[(1030,524),(920,524)],color=C['blue'])
p.edge(a,o1,via=[(920,818),(780,818)],color=C['blue'])
p.edge(a,o2,via=[(920,818),(1030,818)],color=C['blue'])
kr=p.custom('K-R-REGISTER','R','Заявки должны учитываться без потерь',1250,315,220,190,state='Каноническая R',canonical=True)
kc=p.custom('K-C-TEAM','Context','Есть команда, способная развивать сервис',1500,315,210,190,state='Канонический контекст',canonical=True)
a=p.node('A-SERVICE',1370,615,220,home='boundaries')
p.edge(kr,a,via=[(1360,554),(1480,554)],color=C['good'])
p.edge(kc,a,via=[(1605,554),(1480,554)],color=C['good'])
p.text('Условия локальны канону. Тот же Action показан при текущей проверке, без внешнего ref.',1250,858,460,size=18,color=C['muted'])
p.nav('Открыть полный канон ↗','canon',1250,949,460,45)
p.text(f'Под-R - граница раскрытия: «Базовая линза», {page_reference("lens")}. Конечный блок открывает свой граф; identity общая.',65,1051,1670,size=18,color=C['blue'])


# 25 - six concrete obligations of constructing a graph.
p=new('amodel')
p.node('R-L-SEM',675,175,450,165)
p.node('A-L-MODEL',790,490,220)
p.edge('R-L-SEM','A-L-MODEL',color=C['blue'])
for entity,x,y in [('R-L-ROLE',65,220),('R-L-CANONS',65,510),('R-L-QRPE',65,800),('R-L-LINK',1190,220),('R-L-STATE',1190,510),('R-L-TYPES',1190,800)]:
    p.node(entity,x,y,545,175)
    bus=650 if x<900 else 1150
    p.edge('A-L-MODEL',entity,s='left' if x<900 else 'right',t='right' if x<900 else 'left',via=[(bus,600),(bus,y+87.5)],color=C['blue'])
p.node('I-L-RULES',745,895,310,190)
p.edge('I-L-RULES','A-L-MODEL',t='bottom',s='top',dashed=True,color=C['Info'][1])
p.text('Все шесть R обязательны после выбора A-L-MODEL. Клик по R открывает правила проверки её результата.',65,1011,600,size=18,color=C['blue'])
p.text('Общий источник пояснений - I-L-RULES. Это информация, а не отдельная цель и не доказательство выполнения.',1190,1011,545,size=17,color=C['muted'])


# 26 - methods produce results, rather than duplicating the input goal.
p=new('wmethods')
p.panel(65,170,810,905,'Граф A-L-CLARIFY')
p.panel(925,170,810,905,'Граф A-L-EXPLORE')
p.node('R-L-CONTEXT',100,234,740,160)
p.node('R-L-OPTIONS',960,234,740,160)
p.node('A-L-CLARIFY',360,521,220)
p.node('A-L-EXPLORE',1220,521,220)
p.edge('R-L-CONTEXT','A-L-CLARIFY',dashed=True)
p.edge('R-L-OPTIONS','A-L-EXPLORE',dashed=True)
p.custom('R-L-GOALS','R','Цель и достаточность результата уточнены',100,877,350,175,state='На бумаге / не принята',candidate=True)
p.custom('R-L-INPUT','R','Исходные данные и существенные неизвестные явны',490,877,350,175,state='На бумаге / не принята',candidate=True)
p.custom('R-L-SEARCH','R','Набор способов достаточен для оценки',945,877,235,175,state='На бумаге / не принята',candidate=True)
p.custom('R-L-ASSESS','R','Оценки способов имеют основания',1205,877,235,175,state='На бумаге / не принята',candidate=True)
p.custom('R-L-UPSTREAM','R','Последствия для исходных целей оценены',1465,877,235,175,state='На бумаге / не принята',candidate=True)
for entity,x in [('R-L-GOALS',275),('R-L-INPUT',665)]:p.edge('A-L-CLARIFY',entity,via=[(470,820),(x,820)],dashed=True,color=C['blue'])
for entity,x in [('R-L-SEARCH',1062.5),('R-L-ASSESS',1322.5),('R-L-UPSTREAM',1582.5)]:p.edge('A-L-EXPLORE',entity,via=[(1330,820),(x,820)],dashed=True,color=C['blue'])
p.text('Существенные неизвестные выявлены и учтены.',100,760,300,size=16,color=C['muted'])
p.text('Границы поиска обоснованы. Пересмотр исходных целей - явно.',960,760,300,size=16,color=C['muted'])


# 27 - choosing a lens and accounting for it are both explicit work.
p=new('aselect')
p.node('R-L-LENSES',65,175,740,165)
p.node('R-L-USER',995,175,740,165)
p.node('A-L-SELECT',790,495,220)
p.node('I-L-CATALOG',65,565,535,180)
p.edge('R-L-LENSES','A-L-SELECT',via=[(435,408),(900,408)],dashed=True,label='Подобрать применимые линзы',lx=450,ly=379,lw=390)
p.edge('R-L-USER','A-L-SELECT',via=[(1365,448),(900,448)],dashed=True,label='Учесть указанную линзу',lx=1200,ly=419,lw=330)
p.edge('I-L-CATALOG','A-L-SELECT',s='right',t='left',via=[(700,655),(700,605)],dashed=True,color=C['Info'][1])
p.note('Выбрать недостаточно', 'Этот Action включает чтение, выбор и учёт требований линз. Простое открытие каталога не является применением. Несколько линз могут использоваться совместно.',1195,565,540,202,color=C['blue'])
p.custom('R-L-SET','R','Состав применяемых линз обоснован',65,923,740,163,state='На бумаге / не принята',candidate=True)
p.custom('R-L-APPLY','R','Требования выбранных линз учтены в работе',995,923,740,163,state='На бумаге / не принята',candidate=True)
for e,x in [('R-L-SET',435),('R-L-APPLY',1365)]:p.edge('A-L-SELECT',e,via=[(900,850),(x,850)],dashed=True,color=C['blue'])
p.text('Оба выхода обязательны при выборе этого A; чтение линзы не выбирает изображённые в ней рабочие Actions.',65,1100,1670,size=14,color=C['muted'])


# 28 - interpretation modes are self-contained descriptions, never project refs.
p=new('canonmodes')
cols=[(65,280,'Форма условия'),(365,760,'Показательное содержание внутри канона'),(1145,590,'Что устанавливает исполнитель')]
for x,w,t in cols:p.label(t,x,175,w,color=C['ink'],size=18,fill='#E7EDF6')
rows=[('По смыслу','Учёт объектов ведётся без потерь.','Найти R с тем же требуемым результатом; одинаковый заголовок не обязателен.'),('По группе','Требования о сохранности учётных записей.','Обосновать принадлежность реальной R к названной группе.'),('По свойству','R требует сохранности после перезапуска.','Проверить именно это свойство и его область, а не общее сходство тем.'),('Конкретно описанный случай','Требуется работа в закрытой сети; доступ во внешнюю сеть отсутствует.','Сравнить с описанным случаем. Внутри канона нет ref на конкретный рабочий owner.')]
for i,(mode,example,rule) in enumerate(rows):
    y=253+i*157
    p.shape(65,y,1670,139,'#FFFFFF',C['border'],kind='round')
    p.text(mode,85,y+22,250,size=20,bold=True,color=C['purple'])
    p.text(example,385,y+22,720,size=20)
    p.text(rule,1165,y+22,550,size=18,color=C['muted'])
p.note('Роль канона', 'Это показательная ситуация, а не факт проекта. Пример может быть общим или конкретным; локальные R/Context не являются ссылками на рабочие инстансы.',65,915,800,178,color=C['purple'])
p.note('Граница сходства', 'Совпадение по смыслу, частичная связь, несовпадение и неизвестность различаются. Более слабое условие не подтверждает более сильное. Правила ANY/ALL не угадываются.',915,915,820,178,color=C['blue'])


# 29 - closed canonical content; the assessed action is supplied by view context.
p=new('canonpattern')
local=p.panel(65,175,1100,875,'Содержимое канона: только локальные показательные блоки',fill='#FCFAFF',color=C['purple'])
p.custom('K-R-ACCOUNT','R','Учёт объектов типа X ведётся без потерь',105,280,1010,190,state='Шаблон требуемого результата; X - параметр примера',canonical=True)
p.custom('K-C-CAPABLE','Context','Есть команда, способная развивать этот способ учёта',105,545,1010,190,state='Показательное условие; не ссылка на команду проекта',canonical=True)
p.text('AND: описанная цель и возможность развивать способ вместе дают положительный довод. Это не доказательство, что цель уже достигнута.',105,817,1000,size=21,color=C['purple'])
p.text('Ни рабочие R/Context, ни ref на рабочий Action не записаны внутрь канона. Сопоставление выполняется при проверке конкретного способа.',105,957,1000,size=18,color=C['muted'])
p.node('A-SERVICE',1325,570,240,home='canonpattern')
p.edge(local,'A-SERVICE',s='right',t='left',via=[(1240,612),(1240,690)],color=C['good'])
p.note('Текущая проверка', 'Для текущей проверки здесь показан A-SERVICE. Это тот же рабочий Action, а не новый экземпляр. Канон не хранит внешнюю ссылку на него.',1225,175,510,230,color=C['purple'])
p.note('Граница графа канона', 'Граф заканчивается на проверяемом A. Его ситуация и выходные требования открываются на рабочей стороне.',1225,875,510,175,color=C['blue'])


# 30 - comparison belongs to the working side; only real instance refs are dependencies.
p=new('patternmatch')
for x,w,t in [(65,480,'Условие-пример'),(565,535,'Рабочая сущность'),(1120,615,'Вывод проверки')]:p.label(t,x,175,w,size=18,color=C['ink'],fill='#E7EDF6')
rows=[('Учёт объектов X без потерь','R1: заявки регистрируются без потерь','Смысл совпал; X = заявка. R1 - требование, не доказательство достижения.'),('Команда способна развивать способ','C-TEAM v1: команда умеет развивать сервис','Совпало по свойству в учебной ситуации. В рабочей проверке нужен фактический источник.'),('Данные сохраняются после любого сбоя','R-IN: сохранность после перезапуска','Связано частично. Один перезапуск не подтверждает сохранность после любого сбоя.'),('Назначен владелец эксплуатации','C-OPS v1: владелец не назначен','Положительное условие не совпало. Применимо отрицательное условие об отсутствии владельца.')]
for i,row in enumerate(rows):
    y=250+i*143;p.shape(65,y,1670,125,'#FFFFFF',C['border'],kind='round')
    for (x,w),value in zip([(85,440),(585,495),(1140,575)],row):p.text(value,x,y+20,w,size=18,color=C['muted'] if x>1100 else C['ink'])
p.node('C-OPS',65,865,470,175)
p.node('A-SERVICE',1275,835,225)
p.edge('C-OPS','A-SERVICE',s='right',t='bottom',via=[(565,952.5),(565,1093),(1387.5,1093)],dashed=True,color=C['bad'])
p.note('Актуальность оценки A', 'C-OPS → A позволяет заметить изменение факта. Просмотр канона связи не создаёт. При явном применении рабочая сторона хранит CANON_FOR и версию канона: её изменение требует пересмотра оценки A. Канон остаётся локальным; выбора или закрытия автоматически нет.',620,865,560,220,color=C['blue'])


# 31 - a goal, an actual verification method and attached explanatory information.
p=new('rolecheck')
p.node('R-L-SEM',65,175,485,170)
p.node('A-L-MODEL',1260,160,190)
p.node('R-L-ROLE',675,175,450,170)
p.edge('R-L-SEM','R-L-ROLE',s='right',t='left',color=C['blue'])
p.edge('A-L-MODEL','R-L-ROLE',s='left',t='right',color=C['blue'])
p.node('A-L-CHECK-RA',790,865,220)
p.edge('R-L-ROLE','A-L-CHECK-RA',dashed=True)
p.note('R: требуемое утверждение', 'Указаны потребность, смысл, область и достаточность результата. R не подменяется готовым ответом или названием выбранного способа. Условие канона не становится рабочей подцелью ради AND/OR.\nПример R: «Заявки регистрируются без потерь». Варианты «да/нет» относятся к Actions конкретного решения.',65,405,770,390,color=C['blue'])
p.note('Action: конкретный способ', 'Действие понятно по содержанию и действительно служит входящим R. Основание «через ценную декомпозицию» не является самостоятельным способом.\nПример A: «Создать единый сервис заявок». Его собственный граф показывает, какие R он решает, на какие влияет и какие требования вводит.',965,405,770,390,color=C['A'][1])
p.note('Достаточность проверки', 'Для каждого блока можно назвать его роль, источник потребности или содержание действия. Сомнения в смысле уточняются; прошедший validator JSON не заменяет эту проверку.',65,875,600,210,color=C['Info'][1])
p.note('Происхождение R и ситуация Action', 'Происхождение R - исходные R и породивший Action. Ситуация A - относящиеся R с явными ролями и Context. Область оценки A включает сам A, его ситуацию и рассматриваемые каноны.',1135,875,600,210,color=C['Info'][1])


# 32 - two goal views; their methods do not invent facts or obligations.
p=new('canoncheck')
for x,title in [(65,'Граф R-L-CANONS'),(925,'Граф R-L-QRPE')]:p.panel(x,175,810,920,title)
p.node('R-L-CANONS',100,435,740,145)
p.node('R-L-SEM',100,230,350,140,title='Фрагмент построен корректно',state='Исходная R')
p.node('A-L-MODEL',640,230,140,title='Создать',state='Вводит R')
p.edge('R-L-SEM','R-L-CANONS',via=[(275,395),(470,395)],color=C['blue'])
p.edge('A-L-MODEL','R-L-CANONS',via=[(710,395),(470,395)],color=C['blue'])
p.node('R-L-QRPE',960,435,740,145)
p.node('R-L-SEM',960,230,350,140,title='Фрагмент построен корректно',state='Исходная R')
p.node('A-L-MODEL',1500,230,140,title='Создать',state='Вводит R')
p.edge('R-L-SEM','R-L-QRPE',via=[(1135,395),(1330,395)],color=C['blue'])
p.edge('A-L-MODEL','R-L-QRPE',via=[(1570,395),(1330,395)],color=C['blue'])
p.note('Правила сопоставления', 'Канон - самодостаточный показательный граф. Ситуация A содержит реальные относящиеся R и инстансы Context. Сравнение по смыслу, группе или свойству обосновывается. Частичное сходство и неизвестность не объявляются полным совпадением. AND/OR и аргументы против видны явно.',100,625,740,190,color=C['purple'])
p.note('Правила QRPE', 'Вопрос, риск или проблема связан с конкретным предметом проверки и основаниями. Видны существенные неизвестные и состояние. Finding не создаёт скрытое обязательство и не выбирает способ. Если нужна работа, её цель и Action оформляются явно. Если проблем не найдено, сохраняется объём проверки, а не выдуманная запись.',960,625,740,190,color=C['QRPE'][1])
p.node('A-L-BIND',360,850,220)
p.node('A-L-FINDINGS',1220,850,220)
p.edge('R-L-CANONS','A-L-BIND',s='left',via=[(80,507.5),(80,830),(470,830)],dashed=True)
p.edge('R-L-QRPE','A-L-FINDINGS',s='right',via=[(1720,507.5),(1720,830),(1330,830)],dashed=True)


# 33 - three focused R graphs; every terminal Action opens its own further detail.
p=new('linkrules')
checks=[('R-L-LINK','A-L-LINKS','Роли связей','Назначение A: какие R он решает и на какие влияет. Происхождение R: исходные R и породивший A. Роли не выводятся из соседства блоков. Граф R заканчивается на Actions/под-R; граф A - на выходных R; канон - на проверяемом A. Общий инстанс не дублируется.'),('R-L-STATE','A-L-STATES','Факты и обязательства','Нарисован, выбран, размещён во времени, исполнен и закрыт - разные факты. Все выходные R выбранного A обязательны. «Не требуется» оформляется явно. Снятие блокировки не закрывает родителя; лист требует подтверждённого результата.'),('R-L-TYPES','A-L-KINDS','Допустимая модель','Используются только базовые и явно подключённые типы/операции. Название не регистрирует новый kind. Модули остаются в разработке. Целевая диаграмма не разрешает писать Canon/Info/Evidence в текущий runtime обходом его реестра.')]
for i,(r,a,title,body) in enumerate(checks):
    x=65+i*565;p.panel(x,175,540,920,'Собственный граф '+r)
    p.node('R-L-SEM',x+30,235,300,140,title='Фрагмент построен корректно',state='Исходная R')
    p.node('A-L-MODEL',x+370,235,140,title='Создать',state='Вводит R')
    if r=='R-L-STATE':
        p.node('R-L-FACTS',x+30,400,480,115,title='Прослеживаются факты',state='Исходная R')
        p.node(r,x+30,555,480,145)
        p.edge('R-L-FACTS',r,color=C['blue'])
    else:p.node(r,x+30,435,480,145)
    if r=='R-L-STATE':
        p.edge('R-L-SEM',r,via=[(x+180,390),(x+15,390),(x+15,530),(x+270,530)],color=C['blue'])
        p.edge('A-L-MODEL',r,via=[(x+440,390),(x+525,390),(x+525,530),(x+270,530)],color=C['blue'])
    else:
        p.edge('R-L-SEM',r,via=[(x+180,395),(x+270,395)],color=C['blue'])
        p.edge('A-L-MODEL',r,via=[(x+440,395),(x+270,395)],color=C['blue'])
    if r=='R-L-STATE':p.note(title,'Пять разных фактов. Родитель требует подтверждения.',x+30,725,480,110,color=C['Info'][1])
    else:p.note(title,body,x+30,605,480,230,color=C['Info'][1])
    p.node(a,x+160,850,220)
    p.edge(r,a,s='left',via=[(x+15,627.5 if r=='R-L-STATE' else 507.5),(x+15,842),(x+270,842)],dashed=True)


# 34 - fact traceability is a real goal, with direct requirement decomposition.
p=new('factswork')
p.node('R-LENS',65,175,500,165)
p.node('R-L-FACTS',675,430,450,175)
p.edge('R-LENS','R-L-FACTS',s='right',t='left',via=[(605,257.5),(605,517.5)],color=C['blue'])
p.note('Проверяемый результат', 'По состоянию и истории можно понять, что только нарисовано, что принято, что размещено во времени и что действительно подтверждено.',1250,175,485,205,color=C['Info'][1])
p.note('Нужные источники', 'Plan - источник размещения, история - фактов изменений, Evidence - подтверждения указанного результата. Наличие одного не подменяет остальные.',1250,455,485,245,color=C['Info'][1])
p.section('ТРИ НЕПОСРЕДСТВЕННЫЕ ПОД-R; ДАЛЕЕ - ИХ СОБСТВЕННЫЕ ГРАФЫ',65,731,650)
for entity,x in [('R-L-STATE',65),('R-L-HISTORY',650),('R-L-EVIDENCE',1235)]:
    p.node(entity,x,885,500,175)
    p.edge('R-L-FACTS',entity,via=[(900,817),(x+250,817)],color=C['blue'])




# Additional own-R views and explanatory snapshots. No expansion of terminal A outputs here.
for key,r,method,body in [
 ('historygoal','R-L-HISTORY','A-L-AUDIT-HISTORY','Проверить реальные изменения, версии, основания и последовательность. Текущее изображение не доказывает прошлое; повторное открытие не удаляет прежний результат.'),
 ('evidencegoal','R-L-EVIDENCE','A-L-AUDIT-EVIDENCE','Проверить конкретное утверждение, источник, область, версию и ограничения. Ссылка или SHA подтверждает адрес/байты; достаточность результата требует содержательной проверки.')]:
 p=new(key)
 p.node('R-L-FACTS',65,180,460,165)
 p.node(r,660,430,480,180)
 p.edge('R-L-FACTS',r,s='right',t='left',via=[(590,262),(590,520)],label='Прямая подцель',lx=580,ly=365,lw=250,color=C['blue'])
 p.custom(method,'A','Проверить историю' if key=='historygoal' else 'Сверить Evidence',790,790,220,state='Кандидат',candidate=True)
 p.edge(r,method,dashed=True)
 p.note('Достаточность',body,65,680,600,320,color=C['Info'][1])
 p.nav('Пояснение истории' if key=='historygoal' else 'Пояснение Evidence','history' if key=='historygoal' else 'materials',1200,470,500,60)

p=new('truth')
for x,title,state,body in [(65,'t1 / результат подтверждён','Принята / закрыта','Заявка восстановлена после перезапуска; проверка и версия сохранены.'),(655,'t2 / результат утрачен','Принята / открыта','После изменения системы проверка опровергла требуемое утверждение.'),(1245,'t3 / результат восстановлен','Принята / закрыта','Повторная работа и проверка сохранены; используется тот же инстанс R-IN.')]:
 p.panel(x,180,490,720,title)
 p.node('R-IN',x+25,275,440,180,state=state,home='truth')
 p.note('Основание',body,x+25,540,440,210)
p.note('Текущая истина и история','Требуется истинность в указанной области. Старое достижение остаётся фактом истории; текущая R может открыться снова. Для восстановления допустимо вернуться к существующему A. Один stale ещё не доказывает ложность.',65,940,1670,140,color=C['blue'])

p=new('stalechain')
p.note('Условная следующая ветвь того же сервиса', 'A-SERVICE v1 ведёт свой реестр. R1 буквально меняется: «Заявки регистрируются в системе заказчика; второй реестр не ведётся». R2 о понятном статусе сохраняется. После проверки связь R1 → A-SERVICE снята. Это обзор связей, не собственный граф R.',65,158,1670,132,color=C['blue'])
p.panel(65,315,800,600,'До: R1 v1 и R2 реализует общий A')
p.panel(935,315,800,600,'После: та же R1 v2; A пересмотрен')
p.node('R1',95,372,330,145,title='Заявки без потерь',state='v1 / открыта',home='stalechain')
p.node('R2',500,372,330,145,title='Статус понятен',state='v1 / открыта',home='stalechain')
p.node('A-SERVICE',370,554,190,title='Создать сервис',state='v1 / выбран',home='stalechain')
p.edge('R1','A-SERVICE',via=[(260,535),(465,535)])
p.edge('R2','A-SERVICE',via=[(665,535),(465,535)])
for entity,x,title in [('R-IN',95,'Сохранность'),('R-TRACK',350,'Статус виден'),('R-SEC',605,'Права доступа')]:
    p.node(entity,x,790,220,105,title=title,state='Выход A / v1',home='stalechain')
    p.edge('A-SERVICE',entity,via=[(465,765),(x+110,765)],color=C['blue'])
p.node('R1',965,372,330,145,title='Реестр заказчика',state='v2 / тот же ID',home='stalechain')
p.node('R2',1375,372,330,145,title='Статус понятен',state='v1 / тот же ID',home='stalechain')
p.custom('A-REGISTER','A','Связать реестр',1040,554,180,180,state='Новый / выбран')
p.node('A-SERVICE',1415,554,190,title='Показывать статусы',state='v2 / тот же ID',home='stalechain')
p.edge('R1','A-REGISTER',via=[(1130,535)])
p.edge('R2','A-SERVICE',via=[(1540,535),(1510,535)])
for entity,x,title,state in [('R-IN',965,'Сохранность','v2 / открыта'),('R-TRACK',1220,'Статус виден','Пригодна / открыта'),('R-SEC',1475,'Права доступа','Пригодна / открыта')]:
    p.node(entity,x,802,220,105,title=title,state=state,home='stalechain')
    if entity=='R-IN':p.edge('A-REGISTER',entity,via=[(1130,783),(x+110,783)],color=C['blue'])
    else:p.edge('A-SERVICE',entity,via=[(1510,783),(x+110,783)],color=C['blue'])
p.note('Проверяется вся затронутая цепь', 'R1 v2 делает общий A stale. После изменения A проверяются R-IN, R-TRACK, R-SEC и все их реальные зависимые. Учитываются старые и новые связи; цикл обходится конечным числом шагов.',65,935,800,165,color=C['purple'])
p.note('Пересмотр не равен переделке', 'A-SERVICE сохранён для R2; смысл R-TRACK/R-SEC пригоден, цели ещё открыты. R-IN v2 передана новому A-REGISTER и проверяется в новой области. Прежний факт E-REG v1 остаётся в истории.',935,935,800,165,color=C['good'])

p=new('strength')
p.note('Жёсткая несовместимость','R требует работы только в закрытой сети; рассматриваемый A обязательно отправляет данные наружу. Подтверждённое полное условие исключает A в этой ситуации. Плюсы несовместимость не компенсируют.',65,190,810,370,color=C['bad'])
p.note('Мягкий довод против','Команда плохо знает инструмент, необходимый для A. Это повышает цену и риск, но допускает обоснованный выбор с сохранением минуса и мер работы с ним.',925,190,810,370,color=C['A'][1])
p.note('Логическая группа','Для AND сопоставляется вся группа. Совпадение одного элемента не означает выполнение полного условия. OR допускает оба совпадения. Сила относится к доводу относительно A.',65,630,810,300,color=C['purple'])
p.note('Доказанность отдельно','Совпало, частично связано, не совпало и неизвестно - разные результаты. Hard не превращает предположение в факт. Сопоставление не выбирает и не исполняет A автоматически.',925,630,810,300,color=C['teal'])

p=new('decompose')
p.note('Сначала - ценность записи содержания', 'В обоих примерах будущая польза оправдывает запись: (C1 OR C2) AND C3 выполнено. Дальше выбираем полезное разбиение или достаточное описание. Справка и условия канона не становятся рабочими R.',65,160,1670,125,color=C['purple'])
p.panel(65,315,800,650,'Подробная R без бесполезного дробления')
p.node('R-IN',95,365,740,320,state='Учебное уточнение / не подтверждено',home='decompose')
p.text('Область: штатный перезапуск сервиса v2.\nПодтверждённая заявка сохраняет ID, автора, текст и зарегистрированный статус. Проверка сравнивает эти поля до и после перезапуска.\nСбои диска и вложения в этот объём не входят.',115,480,700,size=17,color=C['ink'],parent=p.nodes['R-IN']['id'])
p.note('Почему подробности остались в описании', 'Одна процедура проверяет перечисленные поля вместе. Отдельные под-R сейчас не дают полезного выбора способа или независимого состояния. Если такая польза появится, разбиение можно пересмотреть.',95,715,740,185,color=C['blue'])
p.panel(935,315,800,650,'Сложная R: полезны самостоятельные под-R')
p.custom('R-READY','R','Заявки сохранны, защищены и понятны заявителю',965,365,740,155,state='Учебная сложная R')
for entity,x,title in [('R-DATA',955,'Заявки сохранны'),('R-ACCESS',1215,'Доступ ограничен'),('R-STATUS',1475,'Статус понятен')]:
    p.custom(entity,'R',title,x,615,235,160,state='Свой способ / проверка')
    p.edge('R-READY',entity,via=[(1335,565),(x+117.5,565)],color=C['blue'])
p.note('Почему здесь нужны под-R', 'У сохранности, доступа и понятности разные способы, проверки и состояния. Одно может быть готово раньше другого. Разбиение помогает вести реальную работу; родитель отдельно требует подтверждения.',965,810,740,145,color=C['blue'])
p.note('Приоритет полезного разбиения', 'Если ценное сложное содержание даёт настоящие требуемые утверждения с самостоятельной пользой, предпочитаем под-R. Достаточная подробная R остаётся допустимой; отдельная нода на каждое слово не нужна.',65,990,1670,110,color=C['Info'][1])

p=new('workscopes')
p.panel(65,170,800,840,'Общая работа продолжается: графы соединены')
p.panel(935,170,800,840,'Дальнейшая работа независима: свои экземпляры')
p.text('Один сервис заявок, два рабочих scope. Общий A обеспечивает обе цели.',90,225,750,size=17,color=C['muted'])
p.panel(90,285,325,210,'WG-REG',color=C['blue'])
p.panel(500,285,325,210,'WG-STATUS',color=C['blue'])
p.node('R1',110,350,285,120,title='Заявки без потерь',state='Цель рабочего графа',home='workscopes')
p.node('R2',520,350,285,120,title='Статус понятен',state='Цель рабочего графа',home='workscopes')
p.node('A-SERVICE',355,600,220,home='workscopes')
p.edge('R1','A-SERVICE',via=[(252.5,550),(465,550)])
p.edge('R2','A-SERVICE',via=[(662.5,550),(465,550)])
p.label('Явное соединение scope; один общий A',90,615,235,color=C['blue'],size=16)
p.note('Общее состояние и история', 'A-SERVICE принадлежит общей работе и виден из обоих графов. Один выбор и один фактический результат не превращаются в два события от двух показов.',90,850,735,135,color=C['blue'])
p.text('Условие этой альтернативы: общих будущих работ и обязательств больше нет. Похожие способы будут использоваться независимо.',960,225,750,size=17,color=C['muted'])
p.panel(960,310,325,485,'WG-SUPPORT',color=C['purple'])
p.panel(1375,310,325,485,'WG-EQUIPMENT',color=C['purple'])
p.custom('R-SUPPORT','R','Заявки поддержки учтены',980,375,285,150,state='Независимый объём')
p.custom('R-EQUIPMENT','R','Заявки на оборудование учтены',1395,375,285,150,state='Независимый объём')
p.custom('A-X','A','Настроить учёт',1035,580,180,180,state='Свой экземпляр')
p.custom('A-Y','A','Настроить учёт',1450,580,180,180,state='Другой экземпляр')
p.edge('R-SUPPORT','A-X',via=[(1122.5,550),(1125,550)])
p.edge('R-EQUIPMENT','A-Y',via=[(1537.5,550),(1540,550)])
p.note('Общий способ - разные дальнейшие работы', 'A-X и A-Y могут опираться на один образец, но имеют свои состояния и факты. Если ранее был общий результат, он остаётся общим историческим фактом; его не записывают как два исполнения.',960,825,740,160,color=C['purple'])
p.text('Рабочий граф задаёт scope. Граф R, граф A и граф канона только меняют фокус. Число приложений и совпадение названий сами по себе не определяют identity.',65,1040,1670,size=18,color=C['blue'])


# Explicit origin is metadata of the existing introduction, not a direct child edge.
p=new('originrecord')
p.text('Общий A-SERVICE реализует R1 и R2. Каждый выход обязателен для A; origin уточняет, каким исходным целям он служит.',65,169,1665,size=20,color=C['muted'])
p.panel(65,235,805,430,'Запись выхода R-IN',color=C['blue'])
p.text('DRIVES: R1 → A-SERVICE и R2 → A-SERVICE',90,300,755,size=19,bold=True,color=C['blue'])
p.text('Связь O-IN:\n  type: INTRODUCES\n  from: A-SERVICE\n  to: R-IN\n  origin:\n    role: subgoal\n    requirementIds: [R1]',90,357,755,h=250,size=20)
p.text('R-IN введена через A и является подцелью только R1.\nЭто не прямая DERIVES R1 → R-IN.',90,590,755,h=65,size=18,color=C['muted'])
p.panel(910,235,825,430,'Если A выбран, а выход активен и открыт',color=C['purple'])
rows=[('R-IN','subgoal: [R1]','Блокирует A и R1'),('R-TRACK','subgoal: [R2]','Блокирует A и R2'),('R-SEC','method_correctness','Блокирует A, R1 и R2')]
for i,(rid,role,blocking) in enumerate(rows):
    y=305+i*105
    p.text(rid,935,y,270,size=20,bold=True,color=C['blue'])
    p.text(role,1210,y,490,size=19)
    p.text(blocking,935,y+36,760,size=18,color=C['muted'])
p.text('Все закрытия требуют отдельного подтверждения.\nПустые blockers не создают результата автоматически.',935,610,760,h=50,size=17,color=C['muted'])
p.note('Три собственных графа одной записи', 'У R1 виден конечный A; его выход R-IN здесь не раскрыт. Граф A показывает все выходы. Граф R-IN показывает A и только R1 с ролью подцели через A. Для требования корректности показаны A и все его текущие исходные цели.',65,710,805,230,color=C['blue'])
p.note('Явный пересмотр и совместимость', 'core_output_origin меняет origin существующей связи с историей и проверкой прав. Снятая DRIVES требует пересмотра, не отменяет выход. Прежняя связь без origin читается как unspecified: исходные родители не угадываются. Рабочие owners не мигрируются автоматически.',910,710,825,230,color=C['purple'])
p.nav('Граф R1 ↗','r1',65,1000,450,42)
p.nav('Граф A-SERVICE ↗','aservice',670,1000,450,42)
p.nav('Происхождение R-IN ↗','rin',1285,1000,450,42)


def build_drawio(path):
    mx=ET.Element('mxfile',host='app.diagrams.net',agent='RDG illustrative authoring',version='24.7.17',type='device',compressed='false')
    total_links=0
    for p in pages:
        diagram=ET.SubElement(mx,'diagram',id=PAGE_IDS[p.key],name=p.spec[1])
        model=ET.SubElement(diagram,'mxGraphModel',dx=str(W),dy=str(H),grid='0',gridSize='10',guides='1',tooltips='1',connect='1',arrows='1',fold='1',page='1',pageScale='1',pageWidth=str(W),pageHeight=str(H),background=C['bg'],math='0',shadow='0')
        root=ET.SubElement(model,'root')
        ET.SubElement(root,'mxCell',id='0')
        ET.SubElement(root,'mxCell',id='1',parent='0')
        shapes={o['id']:o for o in p.items if o['type']=='shape'}
        # Panels < relations < nodes, labels and text, consistently with the PDF.
        ordered=([o for o in p.items if o.get('layer')=='background']
                 +[o for o in p.items if o['type']=='edge']
                 +[o for o in p.items if o['type']!='edge' and o.get('layer')!='background'])
        for o in ordered:
            typ=o['type']
            if typ=='edge':
                a=shapes[o['source']]; b=shapes[o['target']]
                sx,sy=o['points'][0];tx,ty=o['points'][-1]
                style=(f'edgeStyle=none;rounded=0;html=0;strokeColor={o["color"]};strokeWidth=2;'
                       f'endArrow={"block" if o["arrow"] else "none"};endFill=1;endSize=9;'
                       f'exitX={(sx-a["x"])/a["w"]:.6f};exitY={(sy-a["y"])/a["h"]:.6f};exitPerimeter=0;'
                       f'entryX={(tx-b["x"])/b["w"]:.6f};entryY={(ty-b["y"])/b["h"]:.6f};entryPerimeter=0;'
                       f'dashed={int(o["dashed"])};dashPattern=6 4;')
                cell=ET.SubElement(root,'mxCell',id=o['id'],style=style,edge='1',parent='1',source=o['source'],target=o['target'])
                geo=ET.SubElement(cell,'mxGeometry',relative='1',**{'as':'geometry'})
                if len(o['points'])>2:
                    arr=ET.SubElement(geo,'Array',**{'as':'points'})
                    for x,y in o['points'][1:-1]: ET.SubElement(arr,'mxPoint',x=str(x),y=str(y))
                continue
            link=o.get('link')
            if typ=='text' and not link and o.get('parent') in shapes:
                link=shapes[o['parent']].get('link')
            holder=root
            if link or o.get('entity'):
                attrs=dict(id=o['id'],label=o['text'] if typ=='text' else '',tooltip=(f'{o.get("entity", "")} - открыть страницу {link}' if link else o.get('entity','')))
                if link:
                    attrs['link']='data:page/id,'+PAGE_IDS[link]
                    total_links+=1
                if o.get('entity'): attrs['entityId']=o['entity']
                holder=ET.SubElement(root,'object',**attrs)
            attr={} if holder is not root else {'id':o['id']}
            parent=o.get('parent') or '1'
            x,y=o['x'],o['y']
            if parent!='1':
                x-=shapes[parent]['x'];y-=shapes[parent]['y']
            if typ=='shape':
                rounded=o['kind']=='round'
                style=(f'shape={"ellipse" if o["kind"]=="ellipse" else "rectangle"};rounded={int(rounded)};'
                       f'arcSize=12;absoluteArcSize=1;whiteSpace=wrap;html=0;'
                       f'fillColor={o["fill"]};strokeColor={o["stroke"] or "none"};strokeWidth={o["sw"]};'
                       f'dashed={int(o["dashed"])};dashPattern=6 4;container=0;')
                cell=ET.SubElement(holder,'mxCell',**attr,style=style,vertex='1',parent=parent)
            else:
                style=(f'text;html=0;strokeColor=none;fillColor=none;align={o["align"]};verticalAlign=middle;'
                       f'whiteSpace=wrap;overflow=hidden;rounded=0;spacing=0;'
                       f'fontFamily=Arial;fontSize={o["size"]};fontStyle={int(o["bold"])};'
                       f'fontColor={o["color"]};resizable=1;')
                if holder is root:attr['value']=o['text']
                cell=ET.SubElement(holder,'mxCell',**attr,style=style,vertex='1',parent=parent)
            ET.SubElement(cell,'mxGeometry',x=f'{x:.3f}',y=f'{y:.3f}',width=f'{o["w"]:.3f}',height=f'{o["h"]:.3f}',**{'as':'geometry'})
    ET.indent(mx,space='  ')
    ET.ElementTree(mx).write(path,encoding='utf-8',xml_declaration=True)
    return total_links


def build_pdf(path):
    pdf=canvas.Canvas(str(path),pagesize=(W,H),pageCompression=1)
    pdf.setTitle('RDG - визуальный пример целевой модели')
    pdf.setAuthor('RDG')
    for p in pages:
        pdf.bookmarkPage(PAGE_IDS[p.key])
        pdf.addOutlineEntry(p.spec[1],PAGE_IDS[p.key],0,False)
        pdf.setFillColor(HexColor(C['bg']));pdf.rect(0,0,W,H,fill=1,stroke=0)
        # Draw base panels, then relations, then nodes/text, keeping relations readable.
        backgrounds=[];foreground=[]
        for o in p.items:
            if o.get('layer')=='background':
                backgrounds.append(o)
            elif o['type']!='edge':
                foreground.append(o)
        # Preserve ordering of cards and their explanatory label panels.
        def draw(o):
            typ=o['type']
            if typ=='shape':
                pdf.setFillColor(HexColor(o['fill']))
                pdf.setStrokeColor(HexColor(o['stroke'] or o['fill']))
                pdf.setLineWidth(o['sw'])
                pdf.setDash([7,5] if o['dashed'] else [])
                x,y,w,h=o['x'],H-o['y']-o['h'],o['w'],o['h']
                if o['kind']=='ellipse': pdf.ellipse(x,y,x+w,y+h,fill=1,stroke=int(bool(o['stroke'])))
                elif o['kind']=='round': pdf.roundRect(x,y,w,h,12,fill=1,stroke=int(bool(o['stroke'])))
                else: pdf.rect(x,y,w,h,fill=1,stroke=int(bool(o['stroke'])))
                pdf.setDash([])
                if o.get('link'):
                    pdf.linkRect('',PAGE_IDS[o['link']],(x,y,x+w,y+h),relative=0,thickness=0)
            elif typ=='text':
                pdf.setFillColor(HexColor(o['color']))
                pdf.setFont('RDG-Bold' if o['bold'] else 'RDG',o['size'])
                x=o['x']; y=H-o['y']-(o['h']-o['size'])/2-o['size']*.80
                if o['align']=='center': pdf.drawCentredString(x+o['w']/2,y,o['text'])
                elif o['align']=='right': pdf.drawRightString(x+o['w'],y,o['text'])
                else: pdf.drawString(x,y,o['text'])
            else:
                pdf.setStrokeColor(HexColor(o['color']));pdf.setFillColor(HexColor(o['color']));pdf.setLineWidth(2)
                pdf.setDash([7,5] if o['dashed'] else [])
                pts=[(x,H-y) for x,y in o['points']]
                path=pdf.beginPath();path.moveTo(*pts[0])
                for xy in pts[1:]:path.lineTo(*xy)
                pdf.drawPath(path,stroke=1,fill=0);pdf.setDash([])
                if o['arrow']:
                    a,b=pts[-2:];angle=math.atan2(b[1]-a[1],b[0]-a[0]);size=10
                    pa=(b[0]-size*math.cos(angle-.4),b[1]-size*math.sin(angle-.4))
                    pb=(b[0]-size*math.cos(angle+.4),b[1]-size*math.sin(angle+.4))
                    path=pdf.beginPath();path.moveTo(*b);path.lineTo(*pa);path.lineTo(*pb);path.close();pdf.drawPath(path,fill=1,stroke=0)
        for o in backgrounds:draw(o)
        for o in p.items:
            if o['type']=='edge':draw(o)
        for o in foreground:draw(o)
        pdf.showPage()
    pdf.save()


def validate_xml(path):
    tree=ET.parse(path);mx=tree.getroot()
    seenpages={x.attrib['id'] for x in mx.findall('diagram')}
    links=0;entities={}
    for d in mx.findall('diagram'):
        ids={o.attrib['id'] for o in d.iter() if 'id' in o.attrib}
        assert len(ids)==len([o for o in d.iter() if 'id' in o.attrib]),d.attrib['name']
        for cell in d.iter('mxCell'):
            for attr in ['parent','source','target']:
                if attr in cell.attrib:assert cell.attrib[attr] in ids,(d.attrib['name'],attr,cell.attrib[attr])
        for o in d.iter('object'):
            if 'link' in o.attrib:
                target=o.attrib['link'].split(',',1)[1]
                assert target in seenpages,target
                links+=1
            if 'entityId' in o.attrib:
                entities.setdefault(o.attrib['entityId'],[]).append(d.attrib['name'])
    return dict(pages=len(seenpages),page_links=links,entity_appearances=sum(map(len,entities.values())),distinct_entities=len(entities),shared_action_views=entities['A-SERVICE'])


if __name__=='__main__':
    drawio=OUT/'RDG-MODEL-EXAMPLE.drawio'
    pdf=OUT/'RDG-MODEL-EXAMPLE.pdf'
    links=build_drawio(drawio)
    build_pdf(pdf)
    report=validate_xml(drawio)
    assert len(pages)==len(PAGES)
    report['files']=[dict(name=x.name,bytes=x.stat().st_size) for x in [drawio,pdf]]
    (QA/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (QA/'scenes.json').write_text(json.dumps([dict(key=p.key,title=p.spec[2],items=p.items) for p in pages],ensure_ascii=False),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
