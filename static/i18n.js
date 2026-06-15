// ════════════════════════════════════════════════════════════════════════
//  i18n — lightweight translations (Russian + English).
//  Static markup carries data-i18n / data-i18n-html / data-i18n-ph attributes;
//  dynamic strings in app.js call t(key, vars) / tPlural(n, key).
// ════════════════════════════════════════════════════════════════════════

const I18N = {
  en: {
    "app.title": "Subscription Sweep — clean up your YouTube",

    "brand.tag.welcome": "Tidy your YouTube subscriptions",
    "brand.tag.triage": "Triage mode",

    // welcome
    "welcome.headline": "Years of subscriptions,<br>sorted in a few minutes.",
    "welcome.lede": "One channel at a time. See the avatar, the name, and — the part that actually decides it — <em>how much you’ve really watched</em>. Keep or remove with a flick. We’ll hand you a clean list at the end.",
    "welcome.f1.k": "No API key",
    "welcome.f1.v": "Nothing to set up in Google Cloud. Just your Takeout export.",
    "welcome.f2.k": "100% local",
    "welcome.f2.v": "Runs on your machine. Your data never leaves it.",
    "welcome.f2.k_hosted": "Private by design",
    "welcome.f2.v_hosted": "Processed for your session only, auto-deleted within 24 hours. Want 100% local? Run the same open-source app on your machine.",
    "welcome.f3.k": "Resumable",
    "welcome.f3.v": "Stop any time. Your progress is saved automatically.",
    "welcome.cta": "Get started",

    // import
    "import.title": "Load your YouTube history",
    "import.sub": "From <a href=\"https://takeout.google.com/\" target=\"_blank\" rel=\"noopener\">Google Takeout</a> — the only data this tool needs.",
    "import.s1": "Open <a href=\"https://takeout.google.com/\" target=\"_blank\" rel=\"noopener\">takeout.google.com</a> and <b>Deselect all</b>, then select only <b>YouTube and YouTube Music</b>.",
    "import.s2": "Click <b>All YouTube data included</b> → keep only <b>subscriptions</b> and <b>history</b>.",
    "import.s3": "Click <b>Multiple formats</b> and set <b>history</b> to <b>JSON</b> <span class=\"hint-inline\">(recommended — gives accurate “last watched” dates)</span>.",
    "import.s4": "Export, wait for the email, download the <b>.zip</b>, and drop it here →",
    "import.dz_title": "Drop your Takeout <b>.zip</b> here",
    "import.dz_or": "or",
    "import.dz_browse": "browse files",
    "import.dz_note": "The whole <code>.zip</code>, or just <code>subscriptions.csv</code> + <code>watch-history.json</code>",
    "import.reading": "Reading {name}…",
    "import.det_subs": "subscriptions",
    "import.det_watch": "watched videos in your history",
    "import.warn_no_subs": "No subscriptions found yet — drop your Takeout .zip, or subscriptions.csv.",
    "import.warn_no_watch": "No watch history detected — the app still works, but the “how much you watched” signal will be empty. Add watch-history.json for the full experience.",
    "import.det_restore": "channels restored from your saved decisions",
    "import.restore_note": "Restoring your saved review — zones and keep/remove/pending decisions come back exactly as you left them. Channel details (thumbnails, subscriber counts) refresh in the background.",
    "import.restore_build": "Restore my review",
    "enrich.bg": "Loading channel previews… {done} / {total}",
    "enrich.bg_done": "✓ Channel previews ready",
    "import.build": "Build my library",
    "import.building": "Building…",
    "import.privacy": "Files are parsed locally and never uploaded.",
    "import.privacy_hosted": "Your file is processed on the server for this session only and deleted automatically within 24 hours.",
    "footer.privacy": "Privacy & data",

    // enrich
    "enrich.title": "Looking up your channels",
    "enrich.sub": "Fetching avatars, last-upload dates and sizes — no API key, straight from YouTube’s public pages.",
    "enrich.channels": "channels",
    "enrich.skip": "Start sorting now →",

    // plan
    "plan.title": "What should we go through?",
    "plan.sub_pre": "You have",
    "plan.sub_post": "subscriptions. We’ve sorted them by how alive each channel is and how much you watch it.",
    "plan.yellow.name": "Needs a look",
    "plan.yellow.tag": "recommended",
    "plan.yellow.desc": "Active channels you barely (or never) watched. The real decisions live here — including forgotten favourites.",
    "plan.red.name": "Probably dead",
    "plan.red.tag": "spot-check",
    "plan.red.desc": "Abandoned channels you never watch — almost all removals. Skim a sample so nothing loved slips through.",
    "plan.red.sample": "Sample 30 at random",
    "plan.red.all": "Review all of them",
    "plan.green.name": "Keepers",
    "plan.green.tag": "rarely needed",
    "plan.green.desc": "Active channels you watch regularly. Kept by default — only review if you’re feeling thorough.",
    "plan.dead.name": "Gone from YouTube",
    "plan.dead.tag": "auto · no swiping",
    "plan.dead.desc": "Deleted or terminated channels. Queued for removal automatically.",
    "plan.queue_pre": "In your queue:",
    "plan.queue_mid": "channels · about",
    "plan.start": "Start sorting",
    "plan.start_over": "Start a new sort",
    "plan.reimport": "↻ Load a different export",
    "plan.reimport_confirm": "Load a different Takeout export? This replaces the current channel list and your decisions.",
    "plan.resume": "← Resume sorting",
    "plan.resume_left": "↩ Continue where you left off · {n} left",
    "plan.resume_review": "↩ Continue to your decisions",
    "plan.new_confirm": "Start a new sort with these categories? Your current progress will be lost.",
    "nav.plan": "↩ Choose categories",
    "nav.home_title": "Change selection / load a different file",
    "plan.window_note": "ⓘ Your watch history covers {from} – {to}. “Never watched” means within that window — older favourites can look colder than they are.",
    "plan.window_note_default": "ⓘ Your watch history covers a limited window — that shapes these estimates.",

    // resume
    "resume.title": "Welcome back.",
    "resume.progress": "You stopped at {voted} of {total}. {left} to go — about {eta}.",
    "resume.continue": "Continue",
    "resume.review": "Review decisions",
    "resume.restart": "Start over",
    "resume.confirm": "Start over? Your current progress will be lost.",

    // swipe
    "swipe.reviewed": "reviewed",
    "swipe.kept": "Kept",
    "swipe.removed": "Removed",
    "swipe.finish": "Finish →",
    "swipe.eta_left": "{eta} left",
    "swipe.done": "done",
    "dock.remove": "Remove",
    "dock.remove_sub": "Unsubscribe",
    "dock.skip": "Skip",
    "dock.undo": "Undo",
    "dock.keep": "Keep",
    "dock.keep_sub": "Stay subscribed",
    "hint.undo": "Undo",
    "hint.drag": "Drag the card, or use",
    "hint.help": "Help",

    // card
    "card.watched_label_one": "video of this channel you watched",
    "card.watched_label_other": "videos of this channel you watched",
    "card.subscribers": "{n} subscribers",
    "card.subs_hidden": "subscribers hidden",
    "card.no_desc": "No description.",
    "fact.watched_k": "You last watched it",
    "fact.watched_never": "never",
    "fact.watched_never_caveat": "never (history since {month})",
    "fact.upload_k": "Channel's last video",
    "fact.upload_none": "no videos",
    "meta.unreachable": "couldn't reach YouTube",
    "stamp.keep": "Keep",
    "stamp.remove": "Cut",
    "peek.next": "Up next",
    "peek.last": "Last one",
    "about.label": "About this channel",

    "liveness.no_videos": "no videos",
    "liveness.this_week": "uploaded this week",
    "liveness.this_month": "uploaded this month",
    "liveness.regularly": "uploads regularly",
    "liveness.slowing": "slowing down",
    "liveness.quiet_year": "quiet ~a year",
    "liveness.dead": "dead 2y+",

    "verdict.keep_strong": "Definitely keep",
    "verdict.keep": "Probably keep",
    "verdict.unsure": "Your call",
    "verdict.drop": "Probably remove",
    "verdict.drop_strong": "Definitely remove",
    "verdict.gone": "Gone from YouTube",

    "aria.card": "{title}. {verdict}. You watched {n} {videos}.",
    "aria.videos_one": "video",
    "aria.videos_other": "videos",
    "aria.kept": "{title} kept.",
    "aria.removed": "{title} removed.",

    "toast.nothing_undo": "Nothing to undo",
    "toast.undone": "Undone — {name} is back",
    "toast.pick_zone": "Pick at least one group to review",
    "toast.all_decided": "Everything in your queue is decided",
    "toast.cant_read": "Couldn’t read that file",

    // review
    "review.title": "Final check",
    "review.sub": "Removing {remove} · keeping {keep} · {pending} not reviewed · {gone} gone from YouTube",
    "review.gone_note": "These channels no longer exist on YouTube — you'll be unsubscribed from them automatically. Nothing to decide here.",
    "review.back": "← Back to sorting",
    "tab.remove": "Removing",
    "tab.keep": "Keeping",
    "tab.pending": "Not reviewed",
    "tab.gone": "Gone from YouTube",
    "sort.label": "Sort",
    "sort.alpha": "A–Z",
    "sort.subs": "Most subscribers",
    "sort.watched": "Most watched by you",
    "sort.recent": "Latest upload",
    "review.search_ph": "Search channels…",
    "review.bulk_keep": "Keep all shown",
    "review.bulk_remove": "Remove all shown",
    "review.bulk_reset": "Reset all shown",
    "review.reset_row": "Reset to not-reviewed (back to the queue)",
    "review.foot": "Unsubscribing from {n} channels. Nothing happens until you export.",
    "review.export": "Export my list →",
    "review.empty": "Nothing here.",
    "badge.kept": "kept",
    "badge.removing": "removing",
    "badge.undecided": "undecided",
    "badge.gone": "gone",
    "row.uploaded": "uploaded {t}",
    "row.no_videos": "no videos",
    "row.watched0": "0 watched",
    "row.watchedN": "watched {n}× · {t}",
    "row.subs": "{n} subs",
    "row.gone": "⚠ Gone from YouTube — channel deleted or banned",

    // done
    "done.title": "Swept.",
    "done.summary": "You had {total} subscriptions. Removing {remove}, keeping {keep}.",
    "done.pick": "Now actually unsubscribe — pick whatever fits you:",
    "done.way_manual_h": "Do it yourself, in the browser",
    "done.way_manual_d": "Opens a page with your list: open a channel, hit “Unsubscribe” on YouTube, tick it off here. Progress is saved — works on any device, nothing to install.",
    "done.way_manual_btn": "Open the unsubscribe page",
    "done.way_manual_dl": "or download a standalone .html",
    "done.way_agent_h": "Hand it to your AI agent",
    "done.way_agent_d": "Download a brief and give it to Claude Code or any agent — it unsubscribes for you (via browser or the YouTube API) and adapts to the current UI.",
    "done.way_agent_btn": "Download the agent brief",
    "done.way_script_h": "Write your own script",
    "done.way_script_d": "A clean JSON list (channel_id, handle, url) to automate against however you like.",
    "done.way_script_btn": "Download unsubscribe.json",
    "done.download": "full decisions.json",
    "done.auto_h": "Or try the built-in automation",
    "done.auto_body": "Drives a real browser via <code>./unsubscribe.sh</code> (macOS/Linux, Python 3.9+). It works, but depends on YouTube's current layout, so it can break after a redesign — the manual page above never does.",
    "done.fineprint": "Tip: run <code>LIMIT=10 ./unsubscribe.sh</code> first to test on 10 channels.",
    "done.hosted_auto": "Want the built-in browser automation too? Run the app locally — same open-source code, one command: <code>./start.sh</code>.",
    "done.back": "← Back to the list",
    "unsub.title": "Unsubscribe",
    "unsub.lead": "Open each channel, hit “Subscribed” → “Unsubscribe” on YouTube — it gets ticked off here automatically. Progress is saved.",
    "unsub.search": "Search channels…",
    "unsub.automark": "Tick off when opened",
    "unsub.hide": "Hide done",
    "unsub.download": "↓ Standalone .html",
    "unsub.progress": "done",
    "unsub.all_done": "All done — every channel ticked off! 🎉",
    "unsub.back": "← Back",
    "unsub.open": "Open ↗",
    "unsub.empty": "Nothing to unsubscribe from.",

    // help
    "help.title": "Keyboard",
    "help.remove": "Remove & next",
    "help.keep": "Keep & next",
    "help.skip": "Skip (comes back later)",
    "help.undo": "Undo last decision",
    "help.open": "Open channel on YouTube",
    "help.finish": "Finish & review",
    "help.close_row": "Close this",
    "help.close": "Close",
    "dialog.ok": "Continue",
    "dialog.cancel": "Cancel",

    // time
    "time.today": "today",
    "time.yesterday": "yesterday",
    "time.d_ago": "{n}d ago",
    "time.mo_ago": "{n}mo ago",
    "time.y_ago": "{n}y ago",
    "time.min": "{n} min",
    "time.hr": "{n} hr",
  },

  ru: {
    "app.title": "Subscription Sweep — чистим подписки YouTube",

    "brand.tag.welcome": "Наведём порядок в подписках YouTube",
    "brand.tag.triage": "Режим разбора",

    // welcome
    "welcome.headline": "Годы подписок —<br>разобрать за пару минут.",
    "welcome.lede": "По одному каналу за раз. Видишь аватарку, название и — то, что и решает дело, — <em>сколько ты его реально смотрел</em>. Свайп — оставить или удалить. В конце получишь чистый список.",
    "welcome.f1.k": "Без API-ключа",
    "welcome.f1.v": "Ничего настраивать в Google Cloud не нужно. Только твой Takeout.",
    "welcome.f2.k": "Всё локально",
    "welcome.f2.v": "Работает на твоём компьютере. Данные никуда не уходят.",
    "welcome.f2.k_hosted": "Приватность по умолчанию",
    "welcome.f2.v_hosted": "Файл обрабатывается только для твоей сессии и автоматически удаляется через 24 часа. Хочешь 100% локально? Запусти то же открытое приложение у себя.",
    "welcome.f3.k": "Можно прерваться",
    "welcome.f3.v": "Останавливайся когда угодно — прогресс сохраняется сам.",
    "welcome.cta": "Поехали",

    // import
    "import.title": "Загрузи свою историю YouTube",
    "import.sub": "Из <a href=\"https://takeout.google.com/\" target=\"_blank\" rel=\"noopener\">Google Takeout</a> — это всё, что нужно приложению.",
    "import.s1": "Открой <a href=\"https://takeout.google.com/\" target=\"_blank\" rel=\"noopener\">takeout.google.com</a>, нажми <b>Отменить выбор</b> и выбери только <b>YouTube and YouTube Music</b>.",
    "import.s2": "Нажми <b>Все данные YouTube</b> → оставь только <b>подписки</b> и <b>историю</b>.",
    "import.s3": "Нажми <b>Несколько форматов</b> и выставь <b>истории</b> формат <b>JSON</b> <span class=\"hint-inline\">(рекомендуется — точные даты «когда смотрел»)</span>.",
    "import.s4": "Экспортируй, дождись письма, скачай <b>.zip</b> и брось его сюда →",
    "import.dz_title": "Перетащи сюда <b>.zip</b> из Takeout",
    "import.dz_or": "или",
    "import.dz_browse": "выбери файлы",
    "import.dz_note": "Весь <code>.zip</code> целиком, или просто <code>subscriptions.csv</code> + <code>watch-history.json</code>",
    "import.reading": "Читаю {name}…",
    "import.det_subs": "подписок",
    "import.det_watch": "просмотренных видео в истории",
    "import.warn_no_subs": "Подписки пока не найдены — брось .zip из Takeout или subscriptions.csv.",
    "import.warn_no_watch": "История просмотров не найдена — приложение всё равно работает, но сигнал «сколько ты смотрел» будет пустым. Добавь watch-history.json для полноты.",
    "import.det_restore": "каналов восстановлено из сохранённых решений",
    "import.restore_note": "Восстанавливаю сохранённый разбор — зоны и решения (оставить / убрать / отложено) вернутся ровно как были. Детали каналов (превью, число подписчиков) подтянутся в фоне.",
    "import.restore_build": "Восстановить разбор",
    "enrich.bg": "Догружаю превью каналов… {done} / {total}",
    "enrich.bg_done": "✓ Превью каналов готовы",
    "import.build": "Собрать библиотеку",
    "import.building": "Собираю…",
    "import.privacy": "Файлы разбираются локально и никуда не загружаются.",
    "import.privacy_hosted": "Файл обрабатывается на сервере только для твоей сессии и автоматически удаляется через 24 часа.",
    "footer.privacy": "Приватность и данные",

    // enrich
    "enrich.title": "Подтягиваю данные каналов",
    "enrich.sub": "Загружаю аватарки, даты последних видео и размеры — без API-ключа, прямо с публичных страниц YouTube.",
    "enrich.channels": "каналов",
    "enrich.skip": "Начать разбор сейчас →",

    // plan
    "plan.title": "Что разбираем?",
    "plan.sub_pre": "У тебя",
    "plan.sub_post": "подписок. Мы отсортировали их по тому, насколько каждый канал жив и сколько ты его смотришь.",
    "plan.yellow.name": "Нужно взглянуть",
    "plan.yellow.tag": "рекомендуем",
    "plan.yellow.desc": "Активные каналы, которые ты почти (или вообще) не смотрел. Здесь и живут настоящие решения — включая забытых любимцев.",
    "plan.red.name": "Скорее мёртвые",
    "plan.red.tag": "выборочно",
    "plan.red.desc": "Заброшенные каналы, которые ты не смотришь, — почти все на удаление. Пробегись по выборке, чтобы не упустить любимое.",
    "plan.red.sample": "Выборка 30 случайных",
    "plan.red.all": "Просмотреть все",
    "plan.green.name": "Любимые",
    "plan.green.tag": "редко нужно",
    "plan.green.desc": "Активные каналы, которые ты смотришь регулярно. Оставляем по умолчанию — заходи только если хочешь основательно.",
    "plan.dead.name": "Удалены с YouTube",
    "plan.dead.tag": "авто · без свайпов",
    "plan.dead.desc": "Удалённые или заблокированные каналы. Поставлены в очередь на удаление автоматически.",
    "plan.queue_pre": "В очереди:",
    "plan.queue_mid": "каналов · примерно",
    "plan.start": "Начать разбор",
    "plan.start_over": "Начать разбор заново",
    "plan.reimport": "↻ Загрузить другой экспорт",
    "plan.reimport_confirm": "Загрузить другой экспорт Takeout? Текущий список каналов и решения будут заменены.",
    "plan.resume": "← Вернуться к разбору",
    "plan.resume_left": "↩ Продолжить с места остановки · осталось {n}",
    "plan.resume_review": "↩ Перейти к моим решениям",
    "plan.new_confirm": "Начать новый разбор с этими категориями? Текущий прогресс будет потерян.",
    "nav.plan": "↩ Выбор категорий",
    "nav.home_title": "Изменить выбор / загрузить другой файл",
    "plan.window_note": "ⓘ Твоя история покрывает {from} – {to}. «Не смотрел» — это в пределах этого окна; старые любимцы могут казаться холоднее, чем есть.",
    "plan.window_note_default": "ⓘ Твоя история покрывает ограниченное окно — это влияет на оценки.",

    // resume
    "resume.title": "С возвращением.",
    "resume.progress": "Ты остановился на {voted} из {total}. Осталось {left} — это примерно {eta}.",
    "resume.continue": "Продолжить",
    "resume.review": "Посмотреть решения",
    "resume.restart": "Начать заново",
    "resume.confirm": "Начать заново? Текущий прогресс будет потерян.",

    // swipe
    "swipe.reviewed": "разобрано",
    "swipe.kept": "Оставлено",
    "swipe.removed": "Удалено",
    "swipe.finish": "Завершить →",
    "swipe.eta_left": "осталось {eta}",
    "swipe.done": "готово",
    "dock.remove": "Удалить",
    "dock.remove_sub": "Отписаться",
    "dock.skip": "Пропустить",
    "dock.undo": "Отменить",
    "dock.keep": "Оставить",
    "dock.keep_sub": "Остаться подписанным",
    "hint.undo": "Отменить",
    "hint.drag": "Тащи карточку или жми",
    "hint.help": "Помощь",

    // card
    "card.watched_label_one": "видео этого канала ты посмотрел",
    "card.watched_label_other": "видео этого канала ты посмотрел",
    "card.subscribers": "{n} подписчиков",
    "card.subs_hidden": "подписчики скрыты",
    "card.no_desc": "Без описания.",
    "fact.watched_k": "Последний раз ты смотрел",
    "fact.watched_never": "ни разу",
    "fact.watched_never_caveat": "ни разу (история с {month})",
    "fact.upload_k": "Последнее видео на канале",
    "fact.upload_none": "нет видео",
    "meta.unreachable": "не удалось проверить на YouTube",
    "stamp.keep": "Оставить",
    "stamp.remove": "Убрать",
    "peek.next": "Дальше",
    "peek.last": "Последний",
    "about.label": "Описание канала",

    "liveness.no_videos": "нет видео",
    "liveness.this_week": "видео на этой неделе",
    "liveness.this_month": "видео в этом месяце",
    "liveness.regularly": "регулярно выкладывает",
    "liveness.slowing": "замедляется",
    "liveness.quiet_year": "тишина ~год",
    "liveness.dead": "мёртв 2+ года",

    "verdict.keep_strong": "Точно оставить",
    "verdict.keep": "Скорее оставить",
    "verdict.unsure": "Твой выбор",
    "verdict.drop": "Скорее удалить",
    "verdict.drop_strong": "Точно удалить",
    "verdict.gone": "Удалён с YouTube",

    "aria.card": "{title}. {verdict}. Ты посмотрел {n} {videos}.",
    "aria.videos_one": "видео",
    "aria.videos_other": "видео",
    "aria.kept": "{title} оставлен.",
    "aria.removed": "{title} удалён.",

    "toast.nothing_undo": "Нечего отменять",
    "toast.undone": "Отменено — {name} вернулся",
    "toast.pick_zone": "Выбери хотя бы одну группу для разбора",
    "toast.all_decided": "Все каналы из очереди уже решены",
    "toast.cant_read": "Не удалось прочитать этот файл",

    // review
    "review.title": "Финальная проверка",
    "review.sub": "Удаляем {remove} · оставляем {keep} · не рассмотрено {pending} · удалены с YouTube {gone}",
    "review.gone_note": "Этих каналов больше нет на YouTube — отпишемся от них автоматически. Здесь ничего решать не нужно.",
    "review.back": "← Назад к разбору",
    "tab.remove": "Удаляем",
    "tab.keep": "Оставляем",
    "tab.pending": "Не рассмотрено",
    "tab.gone": "Удалены с YouTube",
    "sort.label": "Сортировка",
    "sort.alpha": "По алфавиту",
    "sort.subs": "По подписчикам",
    "sort.watched": "По моим просмотрам",
    "sort.recent": "По дате последнего видео",
    "review.search_ph": "Поиск каналов…",
    "review.bulk_keep": "Оставить все",
    "review.bulk_remove": "Удалить все",
    "review.bulk_reset": "Сбросить все",
    "review.reset_row": "Сбросить в «не рассмотрено» (вернуть в очередь)",
    "review.foot": "Отписка от {n} каналов. Ничего не произойдёт, пока не экспортируешь.",
    "review.export": "Выгрузить список →",
    "review.empty": "Здесь пусто.",
    "badge.kept": "оставлен",
    "badge.removing": "удаляется",
    "badge.undecided": "не решено",
    "badge.gone": "удалён",
    "row.uploaded": "видео {t}",
    "row.no_videos": "нет видео",
    "row.watched0": "0 просмотров",
    "row.watchedN": "смотрел {n}× · {t}",
    "row.subs": "{n} подп.",
    "row.gone": "⚠ Удалён с YouTube — канал удалён или забанен",

    // done
    "done.title": "Чисто.",
    "done.summary": "Было {total} подписок. Удаляем {remove}, оставляем {keep}.",
    "done.pick": "Теперь отпишись по-настоящему — выбери, как удобно:",
    "done.way_manual_h": "Сам, прямо в браузере",
    "done.way_manual_d": "Откроется страница со списком: открываешь канал, жмёшь на YouTube «Отписаться», отмечаешь здесь галочкой. Прогресс сохраняется — работает на любом устройстве, ничего ставить не нужно.",
    "done.way_manual_btn": "Открыть страницу отписки",
    "done.way_manual_dl": "или скачать автономный .html",
    "done.way_agent_h": "Поручить своему AI-агенту",
    "done.way_agent_d": "Скачай бриф и отдай Claude Code или любому агенту — он отпишется сам (браузером или через YouTube API) и подстроится под текущий интерфейс.",
    "done.way_agent_btn": "Скачать бриф для агента",
    "done.way_script_h": "Написать свой скрипт",
    "done.way_script_d": "Чистый JSON со списком (channel_id, handle, url) — автоматизируй как удобно.",
    "done.way_script_btn": "Скачать unsubscribe.json",
    "done.download": "полный decisions.json",
    "done.auto_h": "Или попробовать встроенный автомат",
    "done.auto_body": "Управляет настоящим браузером через <code>./unsubscribe.sh</code> (macOS/Linux, Python 3.9+). Работает, но зависит от текущей вёрстки YouTube — после редизайна может сломаться. Страница выше — никогда.",
    "done.fineprint": "Совет: сначала запусти <code>LIMIT=10 ./unsubscribe.sh</code> — проверить на 10 каналах.",
    "done.hosted_auto": "Нужна встроенная автоматизация в браузере? Запусти приложение локально — тот же открытый код, одна команда: <code>./start.sh</code>.",
    "done.back": "← Назад к списку",
    "unsub.title": "Отписка",
    "unsub.lead": "Открывай канал, жми на YouTube «Вы подписаны» → «Отписаться» — здесь он отметится сам. Прогресс сохраняется.",
    "unsub.search": "Поиск каналов…",
    "unsub.automark": "Отмечать при открытии",
    "unsub.hide": "Скрыть готовые",
    "unsub.download": "↓ Автономный .html",
    "unsub.progress": "готово",
    "unsub.all_done": "Готово — все каналы отмечены! 🎉",
    "unsub.back": "← Назад",
    "unsub.open": "Открыть ↗",
    "unsub.empty": "Отписываться не от кого.",

    // help
    "help.title": "Клавиши",
    "help.remove": "Удалить и дальше",
    "help.keep": "Оставить и дальше",
    "help.skip": "Пропустить (вернётся позже)",
    "help.undo": "Отменить последнее решение",
    "help.open": "Открыть канал на YouTube",
    "help.finish": "Завершить и проверить",
    "help.close_row": "Закрыть это окно",
    "help.close": "Закрыть",
    "dialog.ok": "Продолжить",
    "dialog.cancel": "Отмена",

    // time
    "time.today": "сегодня",
    "time.yesterday": "вчера",
    "time.d_ago": "{n} дн. назад",
    "time.mo_ago": "{n} мес. назад",
    "time.y_ago": "{n} г. назад",
    "time.min": "{n} мин",
    "time.hr": "{n} ч",
  },
};

let _lang = "en";

function getLang() { return _lang; }

function detectLang() {
  try { const s = localStorage.getItem("sweep-lang"); if (s === "ru" || s === "en") return s; } catch (e) {}
  return (navigator.language || "").toLowerCase().startsWith("ru") ? "ru" : "en";
}

function t(key, vars) {
  let s = (I18N[_lang] && I18N[_lang][key]) ?? (I18N.en[key] ?? key);
  if (vars) for (const k in vars) s = s.split("{" + k + "}").join(vars[k]);
  return s;
}

function ruPluralIndex(n) {
  const a = n % 10, b = n % 100;
  if (a === 1 && b !== 11) return 0;
  if (a >= 2 && a <= 4 && (b < 10 || b >= 20)) return 1;
  return 2;
}

// Plural via a base key + suffixes _one/_few/_many (ru) or _one/_other (en).
function tPlural(n, base, vars) {
  let suffix;
  if (_lang === "ru") suffix = ["_one", "_few", "_many"][ruPluralIndex(n)];
  else suffix = n === 1 ? "_one" : "_other";
  return t(base + suffix, { n, ...(vars || {}) });
}

function applyI18n(root) {
  root.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
  root.querySelectorAll("[data-i18n-html]").forEach((el) => { el.innerHTML = t(el.dataset.i18nHtml); });
  root.querySelectorAll("[data-i18n-ph]").forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
  root.querySelectorAll("[data-i18n-title]").forEach((el) => { el.title = t(el.dataset.i18nTitle); });
  document.title = t("app.title");
}

// Available languages — add a new one here (plus its dictionary above) and it
// appears in the dropdown automatically. `short` shows in the compact button,
// `name` (endonym) in the menu.
const LANGUAGES = [
  { code: "ru", short: "РУ", name: "Русский" },
  { code: "en", short: "EN", name: "English" },
];
const langByCode = (c) => LANGUAGES.find((l) => l.code === c);

function setLang(lang) {
  _lang = langByCode(lang) ? lang : "en";
  try { localStorage.setItem("sweep-lang", _lang); } catch (e) {}
  document.documentElement.lang = _lang;
  applyI18n(document);
  updateLangDisplay();
  if (window.refreshView) window.refreshView();
}

function updateLangDisplay() {
  const cur = langByCode(_lang) || LANGUAGES[0];
  const code = document.getElementById("lang-code");
  if (code) code.textContent = cur.short;
  document.querySelectorAll("#lang-menu [data-lang]").forEach((li) =>
    li.classList.toggle("active", li.dataset.lang === _lang));
}

// Build + wire the language dropdown (one element, works in the corner or the topbar).
function initLangSwitch() {
  const btn = document.getElementById("lang-current");
  const menu = document.getElementById("lang-menu");
  if (!btn || !menu) return;
  menu.innerHTML = LANGUAGES.map((l) =>
    `<li role="option" data-lang="${l.code}">${l.name}</li>`).join("");
  const close = () => { menu.hidden = true; btn.setAttribute("aria-expanded", "false"); };
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const opening = menu.hidden;
    menu.hidden = !opening;
    btn.setAttribute("aria-expanded", String(opening));
  });
  menu.addEventListener("click", (e) => {
    const li = e.target.closest("[data-lang]");
    if (li) { setLang(li.dataset.lang); close(); }
  });
  document.addEventListener("click", close);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  updateLangDisplay();
}

_lang = detectLang();
