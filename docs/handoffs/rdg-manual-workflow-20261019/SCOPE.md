# Ручной однофайловой workflow — Candidate

Следующий крупный пакет по прямому поручению пользователя: существующий Viewer + явно запускаемый локальный Helper для создания/правки, размещения R/Action, выполнения/отзыва и общей истории. Штатные Graph/Plan writers, права, CAS, journaling/recovery; без автозапуска, shared service, OS/ACL/mount changes и правки пользовательских графов. Новый session-scoped loopback adapter — технический способ первого ручного proof, а не обязательный сервер продукта. Человеческая identity и protected approval им не доказываются.

Проверка: реальный GUI-controller → HTTP → writers на синтетических владельцах; A1 → отзыв → A2; предварительная R; unscheduled result; deny/CAS/retry/revocation/recovery, session/Origin/Host guards, XSS и неизменность исходников при чтении.

По фактической границе Docker/Windows добавлен основной файловый transport выбранной папки на существующем RW mount. Loopback оставлен opt-in, не требованием маршрута. Первый GUI: один graph owner, Plan только R/Actions без старых event/gate/branch constructs. DOM-controller proof отделён от native picker, visual QA и установленного G2.
