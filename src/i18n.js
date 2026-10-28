// The site's wording in Russian and Tajik. The language is picked with the switch in the header and
// remembered in the browser (or ?lang=ru|tj).
const KEY = 'regnum.lang';

const RU = {
  brand: 'Regnum Plaza',
  brandSub: 'Жилой комплекс · Душанбе',
  address: 'ул. Ш. Хусейнзода / ул. И. Нарзикулова, Душанбе',
  loading: 'Загрузка 3D-модели…',
  loadFailed: 'Не удалось загрузить 3D-модель. Проверьте подключение и обновите страницу.',
  noglTitle: 'В этом браузере 3D-просмотр не работает.',
  noglWhy: 'Нужен WebGL 2, а здесь он отключён или не поддерживается.',
  noglHelp: 'Откройте страницу в свежей версии Chrome, Safari, Edge или Firefox или включите аппаратное ускорение в настройках браузера.',
  contextLost: 'Видеокарта остановила 3D-просмотр (не хватило памяти или вкладка долго была в фоне).',
  quality: (high) => (high ? 'Графика: высокая' : 'Графика: лёгкая'),
  qualityTitle: (high) => (high ? 'Переключить на лёгкий режим (быстрее на телефонах и старых компьютерах)' : 'Включить полное качество'),
  complex: 'Весь комплекс',
  blocks: 'Блоки',
  block: (k) => `Блок ${k}`,
  floors: 'Этажи',
  floor: 'Этаж',
  floorN: (n) => `${n} этаж`,
  floorOf: (n, m) => `${n} из ${m}`,
  shops: 'Магазины',
  shopsFloors: '1–2 этажи: магазины',
  flats: (n) => `${n} ${plural(n, 'квартира', 'квартиры', 'квартир')}`,
  flatsOnFloor: (n) => `${n} ${plural(n, 'квартира', 'квартиры', 'квартир')} на этаже`,
  floorsN: (n) => `${n} ${plural(n, 'этаж', 'этажа', 'этажей')}`,
  roomsN: (n) => `${n}-комнатная`,
  roomsShort: (n) => `${n}-комн.`,
  all: 'Все',
  rooms: 'Комнаты',
  chooseTitle: 'Выберите квартиру',
  chooseSub: 'Блоки А, Б и В · квартиры от 1 до 5 комнат',
  chooseNote: 'Нажмите на блок, затем на этаж — этаж откроется в разрезе с мебелью. Выберите квартиру, чтобы увидеть планировку и прогуляться по ней в 3D.',
  stat1: 'квартир',
  stat2: 'м² — площади',
  stat3: 'этажей',
  nearby: 'Рядом с домом',
  neighbourBlock: 'Соседний блок комплекса. Квартиры в блоках А, Б и Г.',
  blockSub: (floors, flats) => `${floors} · ${flats}`,
  blockNote: 'Наведите на этаж и нажмите, чтобы заглянуть внутрь. Или выберите этаж в списке слева.',
  floorNote: 'Нажмите на квартиру на модели или в этом списке.',
  flat: (n) => `Квартира № ${n}`,
  back: '← Назад',
  backTo: (s) => `← ${s}`,
  area: 'Общая площадь',
  ceiling: 'Высота потолков',
  layout: 'Планировка',
  windows: 'Окна выходят',
  walk: '🚶 Прогулка по квартире в 3D',
  siteWalk: '🚶 Прогулка по территории',
  siteWalkBlock: (b) => `🚶 Прогулка у блока ${b}`,
  siteWalkTitle: '<b>Прогулка по территории</b> · Regnum Plaza',
  siteLoading: 'Готовим прогулку…',
  contact: 'Связаться с отделом продаж',
  planZoom: 'Открыть планировку крупно',
  close: 'Закрыть',
  contactToast: 'Контакты отдела продаж появятся здесь. Пока — по телефону застройщика.',
  exitWalk: '✕ Вернуться к зданию',
  hintOverview: 'Перетащите — поворот · Колесо — масштаб · Нажмите на блок',
  hintBlock: 'Нажмите на этаж · Перетащите — поворот · Колесо — масштаб',
  hintFloor: 'Нажмите на квартиру · Перетащите — поворот · Колесо — масштаб',
  walkHelp: 'Перетащите — осмотреться · Нажмите на пол — перейти туда · <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> / стрелки — движение',
  walkHelpSite: 'Перетащите — осмотреться · Нажмите на землю — перейти туда · <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> / стрелки — движение · <kbd>Shift</kbd> — быстрее',
  exitSiteWalk: '✕ Вернуться к комплексу',
  dayTime: 'Время суток',
  hideUi: 'Скрыть панели — останется только вид',
  showUi: 'Показать панели',
  tipFloor: (k, n, m) => `<b>Блок ${k} · ${n} этаж</b><br>${m}`,
  tipBlock: (k) => `<b>Блок ${k}</b>`,
  tipNeighbour: (k) => `<b>Блок ${k}</b><br>соседний блок комплекса`,
  sides: { N: 'на север', E: 'на восток', S: 'на юг', W: 'на запад' },
  m2: 'м²',
  pricePerM2: 'Цена за м²',
  priceTotal: 'Стоимость',
  m: 'м',
  lifts: (n) => `${n} ${plural(n, 'лифт', 'лифта', 'лифтов')}`,
  kg: 'кг',
  summary: { living: 'гостиная', kitchen: 'кухня', bedroom: ['спальня', 'спальни', 'спален'], bath: ['санузел', 'санузла', 'санузлов'], loggia: 'лоджия', terrace: 'терраса', storage: 'гардероб' },
  room: { 'Living room': 'Гостиная', Kitchen: 'Кухня', Bedroom: 'Спальня', Bathroom: 'Ванная', WC: 'Санузел', Hall: 'Холл', Wardrobe: 'Гардероб', Loggia: 'Лоджия', Balcony: 'Балкон', Terrace: 'Терраса' },
  places: { hospital: 'Роддом № 2', school: 'Школа № 20', kindergarten: 'Детский сад' },
  lang: 'RU',
};

const TJ = {
  brand: 'Regnum Plaza',
  brandSub: 'Маҷмааи истиқоматӣ · Душанбе',
  address: 'кӯчаи Ш. Ҳусейнзода / кӯчаи И. Нарзиқулов, Душанбе',
  loading: 'Модели 3D бор мешавад…',
  loadFailed: 'Модели 3D бор нашуд. Пайвастро санҷед ва саҳифаро аз нав кушоед.',
  noglTitle: 'Дар ин браузер намоиши 3D кор намекунад.',
  noglWhy: 'WebGL 2 лозим аст, аммо дар ин ҷо он хомӯш аст ё дастгирӣ намешавад.',
  noglHelp: 'Саҳифаро дар версияи нави Chrome, Safari, Edge ё Firefox кушоед ё суръатбахшии сахтафзориро дар танзимоти браузер фаъол кунед.',
  contextLost: 'Корти видеоӣ намоиши 3D-ро қатъ кард (хотира намерасид ё саҳифа дер боз дар замина буд).',
  quality: (high) => (high ? 'Графика: баланд' : 'Графика: сабук'),
  qualityTitle: (high) => (high ? 'Ба реҷаи сабук гузаштан (барои телефонҳо ва компютерҳои кӯҳна тезтар)' : 'Сифати пурра'),
  complex: 'Тамоми маҷмаа',
  blocks: 'Блокҳо',
  block: (k) => `Блоки ${k}`,
  floors: 'Ошёнаҳо',
  floor: 'Ошёна',
  floorN: (n) => `Ошёнаи ${n}`,
  floorOf: (n, m) => `${n} аз ${m}`,
  shops: 'Мағозаҳо',
  shopsFloors: 'Ошёнаҳои 1–2: мағозаҳо',
  flats: (n) => `${n} хона`,
  flatsOnFloor: (n) => `${n} хона дар ошёна`,
  floorsN: (n) => `${n} ошёна`,
  roomsN: (n) => `${n}-ҳуҷрагӣ`,
  roomsShort: (n) => `${n}-ҳуҷра`,
  all: 'Ҳама',
  rooms: 'Ҳуҷраҳо',
  chooseTitle: 'Хонаро интихоб кунед',
  chooseSub: 'Блокҳои А, Б ва В · хонаҳои 1 то 5-ҳуҷрагӣ',
  chooseNote: 'Ба блок, сипас ба ошёна пахш кунед — ошёна бо мебел дар буриш кушода мешавад. Хонаро интихоб кунед, то нақшаи онро бинед ва дар 3D сайр кунед.',
  stat1: 'хона',
  stat2: 'м² — масоҳат',
  stat3: 'ошёна',
  nearby: 'Дар наздикии хона',
  neighbourBlock: 'Блоки ҳамсояи маҷмаа. Хонаҳо дар блокҳои А, Б ва Г.',
  blockSub: (floors, flats) => `${floors} · ${flats}`,
  blockNote: 'Ба ошёна ишора кунед ва пахш кунед, то ба дарун нигаред. Ё ошёнаро аз рӯйхати чап интихоб кунед.',
  floorNote: 'Ба хона дар модел ё дар ин рӯйхат пахш кунед.',
  flat: (n) => `Хонаи № ${n}`,
  back: '← Бозгашт',
  backTo: (s) => `← ${s}`,
  area: 'Масоҳати умумӣ',
  ceiling: 'Баландии шифт',
  layout: 'Нақша',
  windows: 'Тирезаҳо ба',
  walk: '🚶 Сайри хона дар 3D',
  siteWalk: '🚶 Сайр дар ҳудуди маҷмаа',
  siteWalkBlock: (b) => `🚶 Сайр дар назди блоки ${b}`,
  siteWalkTitle: '<b>Сайр дар ҳудуди маҷмаа</b> · Regnum Plaza',
  siteLoading: 'Сайр омода мешавад…',
  contact: 'Тамос бо шӯъбаи фурӯш',
  planZoom: 'Нақшаро калон кушодан',
  close: 'Пӯшидан',
  contactToast: 'Тамос бо шӯъбаи фурӯш дар ин ҷо пайдо мешавад.',
  exitWalk: '✕ Бозгашт ба бино',
  hintOverview: 'Кашед — гардиш · Чархак — масштаб · Ба блок пахш кунед',
  hintBlock: 'Ба ошёна пахш кунед · Кашед — гардиш · Чархак — масштаб',
  hintFloor: 'Ба хона пахш кунед · Кашед — гардиш · Чархак — масштаб',
  walkHelp: 'Кашед — нигоҳ кунед · Ба фарш пахш кунед — ба он ҷо равед · <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> / тирчаҳо — ҳаракат',
  walkHelpSite: 'Кашед — нигоҳ кунед · Ба замин пахш кунед — ба он ҷо равед · <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> / тирчаҳо — ҳаракат · <kbd>Shift</kbd> — тезтар',
  exitSiteWalk: '✕ Бозгашт ба маҷмаа',
  dayTime: 'Вақти шабонарӯз',
  hideUi: 'Пинҳон кардани панелҳо — танҳо манзара мемонад',
  showUi: 'Нишон додани панелҳо',
  tipFloor: (k, n, m) => `<b>Блоки ${k} · ошёнаи ${n}</b><br>${m}`,
  tipBlock: (k) => `<b>Блоки ${k}</b>`,
  tipNeighbour: (k) => `<b>Блоки ${k}</b><br>блоки ҳамсояи маҷмаа`,
  sides: { N: 'шимол', E: 'шарқ', S: 'ҷануб', W: 'ғарб' },
  m2: 'м²',
  pricePerM2: 'Нарх барои м²',
  priceTotal: 'Арзиш',
  m: 'м',
  lifts: (n) => `${n} лифт`,
  kg: 'кг',
  summary: { living: 'меҳмонхона', kitchen: 'ошхона', bedroom: ['хонаи хоб', 'хонаи хоб', 'хонаи хоб'], bath: ['ҳаммом', 'ҳаммом', 'ҳаммом'], loggia: 'айвон', terrace: 'терраса', storage: 'либосхона' },
  room: { 'Living room': 'Меҳмонхона', Kitchen: 'Ошхона', Bedroom: 'Хонаи хоб', Bathroom: 'Ҳаммом', WC: 'Ҳоҷатхона', Hall: 'Даҳлез', Wardrobe: 'Либосхона', Loggia: 'Айвон', Balcony: 'Балкон', Terrace: 'Айвони кушода' },
  places: { hospital: 'Таваллудхонаи № 2', school: 'Мактаби № 20', kindergarten: 'Боғчаи кӯдакона' },
  lang: 'TJ',
};

export function plural(n, one, few, many) {
  const m10 = n % 10, m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return one;
  if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return few;
  return many;
}

const DICTS = { ru: RU, tj: TJ };

function detect() {
  const q = new URLSearchParams(location.search).get('lang');
  if (q === 'ru' || q === 'tj') return q;
  try {
    const s = localStorage.getItem(KEY);
    if (s === 'ru' || s === 'tj') return s;
  } catch {
    // storage blocked
  }
  return 'ru';
}

let lang = detect();
export const L = () => DICTS[lang];
export const getLang = () => lang;
export function setLang(l) {
  lang = l;
  try {
    localStorage.setItem(KEY, l);
  } catch {
    // not remembered
  }
  document.documentElement.lang = l === 'tj' ? 'tg' : 'ru';
}
document.documentElement.lang = lang === 'tj' ? 'tg' : 'ru';

/** 150.35 -> "150,35" */
export const num = (x) => x.toLocaleString('ru-RU', { maximumFractionDigits: 2 });
