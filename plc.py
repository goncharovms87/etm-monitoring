import collections.abc
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

# 1. Инициализация презентации 16:9
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

# Корпоративная палитра КЭАЗ
COLOR_BLUE = RGBColor(10, 10, 240)       # #0A0AF0 Основной синий КЭАЗ
COLOR_ORANGE = RGBColor(255, 70, 0)      # #FF4600 Акцентный оранжевый
COLOR_DARK = RGBColor(11, 34, 64)        # #0B2240 Темно-синий графит
COLOR_CYAN = RGBColor(3, 153, 255)       # #0399FF Вспомогательный голубой
COLOR_GRAY_BG = RGBColor(244, 246, 249)  # Светло-серый фон карточек
COLOR_BORDER = RGBColor(207, 218, 226)   # Границы
COLOR_WHITE = RGBColor(255, 255, 255)
COLOR_TEXT_MUTED = RGBColor(90, 104, 120)

blank_layout = prs.slide_layouts[6]

def add_header_and_footer(slide, title_text, subtitle_text, slide_num):
    # Шапка
    tb = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(9.5), Inches(0.9))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
    
    p = tf.paragraphs[0]
    p.text = title_text
    p.font.name = 'Arial'
    p.font.size = Pt(20)
    p.font.bold = True
    p.font.color.rgb = COLOR_BLUE
    
    p2 = tf.add_paragraph()
    p2.text = subtitle_text
    p2.font.name = 'Arial'
    p2.font.size = Pt(11)
    p2.font.color.rgb = COLOR_TEXT_MUTED
    p2.space_before = Pt(3)

    # Логотип КЭАЗ 80
    logo_box = slide.shapes.add_textbox(Inches(10.8), Inches(0.4), Inches(1.8), Inches(0.7))
    ltf = logo_box.text_frame
    ltf.margin_left = ltf.margin_top = ltf.margin_right = ltf.margin_bottom = 0
    lp = ltf.paragraphs[0]
    lp.text = "КЭАЗ 80"
    lp.font.name = 'Arial'
    lp.font.size = Pt(20)
    lp.font.bold = True
    lp.font.color.rgb = COLOR_BLUE
    lp.alignment = PP_ALIGN.RIGHT
    
    lp2 = ltf.add_paragraph()
    lp2.text = "ОСНОВАН В 1945"
    lp2.font.name = 'Arial'
    lp2.font.size = Pt(7)
    lp2.font.bold = True
    lp2.font.color.rgb = COLOR_DARK
    lp2.alignment = PP_ALIGN.RIGHT

    # Разделитель шапки
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.35), Inches(11.733), Inches(0.02))
    line.fill.solid()
    line.fill.fore_color.rgb = COLOR_GRAY_BG
    line.line.color.rgb = COLOR_GRAY_BG

    # Подвал
    foot_line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(6.85), Inches(11.733), Inches(0.015))
    foot_line.fill.solid()
    foot_line.fill.fore_color.rgb = COLOR_BORDER
    foot_line.line.color.rgb = COLOR_BORDER

    ftb = slide.shapes.add_textbox(Inches(0.8), Inches(6.9), Inches(11.733), Inches(0.3))
    ftf = ftb.text_frame
    ftf.margin_left = ftf.margin_top = ftf.margin_right = ftf.margin_bottom = 0
    fp = ftf.paragraphs[0]
    fp.text = f"Продуктовая стратегия • Переход на платформу RK3568          |          КОНФИДЕНЦИАЛЬНО          |          Слайд {slide_num} из 14"
    fp.font.name = 'Arial'
    fp.font.size = Pt(9)
    fp.font.color.rgb = COLOR_TEXT_MUTED

def create_card(slide, left, top, width, height, title, text_items, is_accent=False, is_dark=False):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    card.fill.solid()
    
    if is_dark:
        card.fill.fore_color.rgb = COLOR_DARK
        border_color = COLOR_CYAN
    elif is_accent:
        card.fill.fore_color.rgb = RGBColor(255, 248, 245)
        border_color = COLOR_ORANGE
    else:
        card.fill.fore_color.rgb = COLOR_GRAY_BG
        border_color = COLOR_BLUE
        
    card.line.color.rgb = border_color
    card.line.width = Pt(1.5)

    tb = slide.shapes.add_textbox(Inches(left + 0.15), Inches(top + 0.15), Inches(width - 0.3), Inches(height - 0.3))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

    p = tf.paragraphs[0]
    p.text = title
    p.font.name = 'Arial'
    p.font.size = Pt(12)
    p.font.bold = True
    p.font.color.rgb = COLOR_WHITE if is_dark else (COLOR_ORANGE if is_accent else COLOR_BLUE)

    for item in text_items:
        p2 = tf.add_paragraph()
        p2.text = f"• {item}"
        p2.font.name = 'Arial'
        p2.font.size = Pt(10)
        p2.font.color.rgb = RGBColor(220, 225, 230) if is_dark else COLOR_DARK
        p2.space_before = Pt(4)

# ==================== СЛАЙД 1. ТИТУЛ ====================
s1 = prs.slides.add_slide(blank_layout)
bg1 = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
bg1.fill.solid()
bg1.fill.fore_color.rgb = COLOR_DARK
bg1.line.fill.background()

t_box = s1.shapes.add_textbox(Inches(1.0), Inches(1.8), Inches(11.3), Inches(3.5))
tf1 = t_box.text_frame
tf1.word_wrap = True
p = tf1.paragraphs[0]
p.text = "ПРОДУКТОВАЯ СТРАТЕГИЯ • АСУ ТП"
p.font.name = 'Arial'
p.font.size = Pt(13)
p.font.bold = True
p.font.color.rgb = COLOR_ORANGE

p2 = tf1.add_paragraph()
p2.text = "ПЛК OptiSmart U и OptiSmart AI"
p2.font.name = 'Arial'
p2.font.size = Pt(38)
p2.font.bold = True
p2.font.color.rgb = COLOR_WHITE
p2.space_before = Pt(10)

p3 = tf1.add_paragraph()
p3.text = "Обоснование инвестиций в R&D собственной процессорной платформы SoM Rockchip RK3568,\nинтеграции среды Gauss 2.0 / SEVON SS и соответствия критериям ПАК по ПП РФ № 719"
p3.font.name = 'Arial'
p3.font.size = Pt(16)
p3.font.color.rgb = COLOR_CYAN
p3.space_before = Pt(15)

p4 = tf1.add_paragraph()
p4.text = "Инвестиции CAPEX: 7,0 млн руб.  |  Окупаемость с учетом продаж силы КЭАЗ: <18 мес.  |  Горизонт: 2026–2031 гг."
p4.font.name = 'Arial'
p4.font.size = Pt(12)
p4.font.color.rgb = COLOR_WHITE
p4.space_before = Pt(30)

# ==================== СЛАЙД 2. ПРОБЛЕМАТИКА ====================
s2 = prs.slides.add_slide(blank_layout)
add_header_and_footer(s2, "Стратегический вызов: исчерпание потенциала OEM Wiren Board", "Предпосылки перехода к собственной схемотехнике и разработке ПАК", 2)
create_card(s2, 0.8, 1.6, 3.7, 4.8, "1. Ценовой тупик Wiren Board", [
    "OptiSmart PLC-2 напрямую идентифицируется как контроллер WB.",
    "В конкурсных процедурах заказчик видит открытую цену сайта WB и требует дисконт.",
    "Маржинальность КЭАЗ размывается, статус системного вендора теряется."
], is_accent=True)
create_card(s2, 4.8, 1.6, 3.7, 4.8, "2. Барьеры OptiLogic L", [
    "Медленный процессор не справляется с возросшим числом тегов.",
    "Отсутствуют высокоскоростные шины (PCIe, SATA, USB 3.0).",
    "Невозможно реализовать локальный Web HMI и буферизацию Store & Forward."
])
create_card(s2, 8.8, 1.6, 3.7, 4.8, "3. Решение на SoM RK3568", [
    "Плата собственной разработки в корпусе OptiLogic L CPU-3.",
    "Полный разрыв прямой ценовой связи с каталогом Wiren Board.",
    "Аппаратный NPU для Edge AI и соответствие критериям ПАК (ПП № 719)."
], is_dark=True)

# ==================== СЛАЙД 3. ДОРОЖНАЯ КАРТА ====================
s3 = prs.slides.add_slide(blank_layout)
add_header_and_footer(s3, "Этапы развития автоматизации и контрольные точки R&D", "Хронология перехода на независимую аппаратную платформу КЭАЗ", 3)
quarters = ["Q4-2026", "Q1-2027", "Q2-2027", "Q3-2027", "Q4-2027"]
tasks = [
    "ТЗ на Carrier Board под SoM RK3568, тепловое моделирование",
    "Первый прототип платы, стресс-тесты в герметичном корпусе",
    "Портирование Linux BSP, интеграция ПО Gauss 2.0 / SEVON SS",
    "Сертификация ТР ТС 004/020, опытная партия 50 шт., тест в СЩО",
    "Серийный выпуск OptiSmart U/AI, вывод в реестр Минпромторга"
]
for i in range(5):
    left = 0.8 + i * 2.4
    card = s3.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(1.6), Inches(2.2), Inches(4.8))
    card.fill.solid()
    card.fill.fore_color.rgb = COLOR_GRAY_BG if i < 4 else RGBColor(235, 245, 255)
    card.line.color.rgb = COLOR_ORANGE if i == 0 else (COLOR_BLUE if i == 4 else COLOR_BORDER)
    
    tb = s3.shapes.add_textbox(Inches(left + 0.1), Inches(1.7), Inches(2.0), Inches(4.5))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = quarters[i]
    p.font.name = 'Arial'
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = COLOR_ORANGE if i == 0 else COLOR_BLUE
    
    p2 = tf.add_paragraph()
    p2.text = tasks[i]
    p2.font.name = 'Arial'
    p2.font.size = Pt(10)
    p2.font.color.rgb = COLOR_DARK
    p2.space_before = Pt(8)

# ==================== СЛАЙД 4. БЕНЧМАРК ====================
s4 = prs.slides.add_slide(blank_layout)
add_header_and_footer(s4, "Аппаратный бенчмарк: Wiren Board 7 vs OptiLogic L vs RK3568", "Техническое сравнение платформ и преодоление ограничений", 4)
rows, cols = 7, 5
table_shape = s4.shapes.add_table(rows, cols, Inches(0.8), Inches(1.6), Inches(11.733), Inches(4.8))
table = table_shape.table
headers = ["Параметр", "Wiren Board 7 (WB-7)", "OptiLogic L (CPU-2/3)", "OptiSmart U/AI (RK3568)", "Эффект для КЭАЗ"]
for col_idx, h in enumerate(headers):
    cell = table.cell(0, col_idx)
    cell.fill.solid()
    cell.fill.fore_color.rgb = COLOR_BLUE
    p = cell.text_frame.paragraphs[0]
    p.text = h
    p.font.name = 'Arial'
    p.font.size = Pt(10)
    p.font.bold = True
    p.font.color.rgb = COLOR_WHITE

data_bm = [
    ["Архитектура CPU", "Allwinner H616 (4× A53, 1.5 ГГц)", "ARM Cortex-M4 / Linux (<400 МГц)", "4× Cortex-A55, 2.0 ГГц (22 нм)", "Рост быстродействия при низком нагреве"],
    ["ИИ-модуль (NPU)", "Отсутствует (0 TOPS)", "Отсутствует (0 TOPS)", "Аппаратный NPU 0.8–1.0 TOPS", "Уникальное УТП предиктивной аналитики"],
    ["Память RAM/Flash", "1–2 ГБ / 8–64 ГБ eMMC", "128–256 МБ / Flash", "2–4 ГБ LPDDR4 / 32–64 ГБ eMMC", "Поддержка тяжелых БД Store & Forward"],
    ["Шины данных", "Только USB 2.0", "Внутренняя медленная шина", "PCIe 3.0, SATA 3.0, USB 3.0", "Подключение NVMe SSD накопителей"],
    ["Ethernet", "2× 100M (общий коммутатор)", "1× 100M Ethernet", "2× 1000M GbE (раздельные MAC)", "Изоляция сети автоматики от IT-сети"],
    ["Корпус изделия", "Корпус WB (открытый рынок)", "Корпус OptiLogic L DIN", "Использование корпуса OptiLogic L", "Экономия 2,4 млн руб. на оснастке"]
]
for row_idx, row_data in enumerate(data_bm):
    for col_idx, text in enumerate(row_data):
        cell = table.cell(row_idx + 1, col_idx)
        cell.fill.solid()
        cell.fill.fore_color.rgb = COLOR_WHITE if row_idx % 2 == 0 else COLOR_GRAY_BG
        p = cell.text_frame.paragraphs[0]
        p.text = text
        p.font.name = 'Arial'
        p.font.size = Pt(9.5)
        p.font.color.rgb = COLOR_DARK

# ==================== СЛАЙД 5. СЕГМЕНТАЦИЯ ====================
s5 = prs.slides.add_slide(blank_layout)
add_header_and_footer(s5, "Сегментация заказчиков и структура применения ПЛК", "Распределение парка контроллеров по ключевым отраслям РФ", 5)
create_card(s5, 0.8, 1.6, 2.7, 4.8, "Строительство / BMS", [
    "BMS-системы: 45%",
    "Общепром (насосы/вент): 20%",
    "Интеллектуальное НКУ: 15%",
    "Прочие системы: 20%",
    "Фокус: диспетчеризация энергоснабжения и магистральные шлюзы."
])
create_card(s5, 3.8, 1.6, 2.7, 4.8, "Промышленность", [
    "Общепром (линии/станки): 50%",
    "Прочие типы ПЛК: 30%",
    "Интеллектуальное НКУ: 10%",
    "BMS площадок: 10%",
    "Фокус: учет электроэнергии, вибродиагностика и предиктивный анализ."
], is_accent=True)
create_card(s5, 6.8, 1.6, 2.7, 4.8, "Энергетика / Сети", [
    "Спец. контроллеры: 55%",
    "Общепромышленные: 30%",
    "Интеллектуальное НКУ: 10%",
    "BMS подстанций: 5%",
    "Фокус: ячейки КРУ, телемеханика и термомониторинг шин."
])
create_card(s5, 9.8, 1.6, 2.7, 4.8, "ЦОД / Серверные", [
    "Спец. контроллеры: 40%",
    "BMS здания: 25%",
    "Edge / Мониторинг НКУ: 20%",
    "Общепром: 15%",
    "Фокус: контроль PDU, бесперебойность, климат стоек."
], is_dark=True)

# ==================== СЛАЙД 6. АРХИТЕКТУРА 1: НКУ ====================
s6 = prs.slides.add_slide(blank_layout)
add_header_and_footer(s6, "Архитектура решения: Интеллектуальное НКУ (ГРЩ/ВРУ)", "ПЛК как драйвер поставок силовой аппаратуры КЭАЗ", 6)
create_card(s6, 0.8, 1.6, 7.5, 4.8, "Структурная декомпозиция решения (Бюджет 100%)", [
    "L1: Силовая часть (38%) [КЭАЗ]: шкафы НКУ, выключатели OptiMat (A, D, T) с MR-расцепителями, контакторы.",
    "L0: Полевой уровень (20%) [КЭАЗ 75% / Стороннее 25%]: счетчики OptiMer, термометрия шин OptiSmart THM/Tag.",
    "L2: Автоматизация (14%) [КЭАЗ]: ПЛК OptiSmart U/AI + модули дискретного ввода OptiLogic L.",
    "L3/L4: ПО и Web (10%) [КЭАЗ]: среда Gauss 2.0 / SEVON SS, встроенная мнемосхема щита, ИИ-модули гармоник.",
    "Инжиниринг и ПНР (18%) [Партнеры СЩО]: сборка шкафа, вторичная коммутация, параметрирование."
])
create_card(s6, 8.6, 1.6, 3.9, 4.8, "Рынок и Заказчики", [
    "Ключевые заказчики: Россети, Сибур, Лукойл, НЛМК, Еврохим, региональные щитовики.",
    "Доли рынка сегмента: Systeme Electric — 32%, ОВЕН — 28%, Wiren Board — 25%, Другие — 15%.",
    "Роль ПЛК: «Проектный замок». Закрытый артикул защищает силовую часть КЭАЗ на сумму в 4–6 раз выше стоимости ПЛК."
], is_accent=True)

# ==================== СЛАЙД 7. АРХИТЕКТУРА 2: BMS GATEWAY ====================
s7 = prs.slides.add_slide(blank_layout)
add_header_and_footer(s7, "Архитектура решения: BMS Edge Gateway", "Координация этажей здания и интеграция разнородных протоколов", 7)
create_card(s7, 0.8, 1.6, 7.5, 4.8, "Структурная декомпозиция решения (Бюджет 100%)", [
    "L1: Силовая часть (15%) [КЭАЗ]: этажные распределительные щиты, модульные автоматы OptiDin.",
    "L0: Полевой уровень (22%) [Стороннее 80% / КЭАЗ 20%]: счетчики тепла/воды, датчики температуры, приводы заслонок.",
    "L2: Автоматизация (25%) [КЭАЗ 70% / Стороннее 30%]: головной шлюз OptiSmart U + модули ввода-вывода.",
    "L3/L4: ПО интеграции (16%) [КЭАЗ 60% / Стороннее 40%]: Gauss 2.0 (BACnet/IP, MQTT, Modbus TCP) в SCADA.",
    "Инжиниринг и ПНР (22%) [Интеграторы]: привязка до 2000 тегов, наладка расписаний и сценариев."
])
create_card(s7, 8.6, 1.6, 3.9, 4.8, "Рынок и Заказчики", [
    "Ключевые заказчики: девелоперы коммерческой недвижимости (ПИК, Самолёт, MR Group, Инград).",
    "Доли рынка сегмента: Зарубежные (Siemens/Niagara) — 30%, Альфа Инжиниринг — 22%, Carel — 18%, Другие — 30%.",
    "Преимущество КЭАЗ: наличие 2 независимых GbE-портов для изоляции технологической сети здания от IT-контура."
])

# ==================== СЛАЙД 8. АРХИТЕКТУРА 3: КРИТИЧЕСКАЯ ИНФРАСТРУКТУРА ====================
s8 = prs.slides.add_slide(blank_layout)
add_header_and_footer(s8, "Архитектура решения: Насосные станции (АУПТ/ХВС) и ИТП", "Автоматизация ответственных технологических узлов здания", 8)
create_card(s8, 0.8, 1.6, 7.5, 4.8, "Структурная декомпозиция решения (Бюджет 100%)", [
    "L1: Силовая часть (32%) [КЭАЗ]: шкафы управления ШУД, выключатели OptiMat, ЧРП OptiCor, устройства АВР.",
    "L0: Полевой уровень (18%) [Стороннее 85% / КЭАЗ 15%]: датчики давления 4–20 мА, термопары Pt100, приводы клапанов.",
    "L2: Автоматизация (16%) [КЭАЗ]: OptiSmart U (алгоритмы каскадного пуска) + быстрые модули OptiLogic L.",
    "L3/L4: ПО рантайма (12%) [КЭАЗ]: Gauss 2.0; поддержка ядра Astra IDE (CODESYS) для промышленных ТЗ.",
    "Инжиниринг (22%) [Отраслевые интеграторы]: балансировка контуров ПИД-регулирования, шеф-монтаж."
])
create_card(s8, 8.6, 1.6, 3.9, 4.8, "Рынок и Заказчики", [
    "Ключевые заказчики: Мосводоканал, ГУП ТЭК, водоканалы городов миллионников, крупные ТРЦ.",
    "Доли рынка сегмента: Segnetics — 35%, Systeme Electric — 25%, ОВЕН — 20%, Другие — 20%.",
    "Преимущество КЭАЗ: поставка комплектного шкафа с ЧРП OptiCor и силовой коммутацией завода."
], is_accent=True)

# ==================== СЛАЙД 9. АРХИТЕКТУРА 4: EDGE / ЦОД ====================
s9 = prs.slides.add_slide(blank_layout)
add_header_and_footer(s9, "Архитектура решения: Edge-контроллеры для ЦОД и серверных", "Предиктивный мониторинг питания и стойки на базе OptiSmart AI", 9)
create_card(s9, 0.8, 1.6, 7.5, 4.8, "Структурная декомпозиция решения (Бюджет 100%)", [
    "L1: Силовое распределение (28%) [КЭАЗ]: распределительные шкафы PDU, вводные шкафы ВРУ, автоматы OptiMat A.",
    "L0: Полевой уровень (24%) [Стороннее 70% / КЭАЗ 30%]: измерители сети OptiMer, датчики стоек, датчики протечки.",
    "L2: Edge-контроллер (20%) [КЭАЗ]: OptiSmart AI со встроенным NPU для локального энергоанализа.",
    "L3/L4: ПО DCIM (13%) [КЭАЗ 50% / Стороннее 50%]: передача метрик по SNMPv3 / MQTT в систему управления ЦОД.",
    "Инжиниринг (15%) [Специализированные интеграторы]: ПНР каналов связи, интеграция с ИБП и ДГУ."
])
create_card(s9, 8.6, 1.6, 3.9, 4.8, "Рынок и Заказчики", [
    "Ключевые заказчики: Ростелеком-ЦОД, IXcellerate, Сбер, Яндекс, корпоративные серверные.",
    "Доли рынка сегмента: Параллельный импорт (Schneider/Vertiv) — 35%, ОВЕН/Fastwel — 25%, ПромПК — 25%, Другие — 15%.",
    "Преимущество КЭАЗ: расчет остаточного ресурса контактов и локальный пик-шейвинг без передачи данных во внешнее облако."
], is_dark=True)

# ==================== СЛАЙД 10. РАЗРЫВЫ И ПОРТФЕЛЬ ====================
s10 = prs.slides.add_slide(blank_layout)
add_header_and_footer(s10, "Оценка рынка комплексных решений и продуктовые разрывы", "Анализ объемов закупки в РФ и потенциал закрытия каталогом keaz.ru", 10)
rows, cols = 5, 5
table_shape = s10.shapes.add_table(rows, cols, Inches(0.8), Inches(1.6), Inches(11.733), Inches(3.4))
t10 = table_shape.table
headers10 = ["Типовое решение", "Объем в РФ (год)", "Средний чек", "Закрыто в keaz.ru", "Продуктовые разрывы (стороннее)"]
for col_idx, h in enumerate(headers10):
    cell = t10.cell(0, col_idx)
    cell.fill.solid()
    cell.fill.fore_color.rgb = COLOR_BLUE
    p = cell.text_frame.paragraphs[0]
    p.text = h
    p.font.name = 'Arial'
    p.font.size = Pt(9.5)
    p.font.bold = True
    p.font.color.rgb = COLOR_WHITE

data_gap = [
    ["Умное НКУ (ГРЩ/ВРУ)", "~18 000 шкафов", "0,65 – 1,4 млн ₽", "До 60% чека (OptiMat, шкафы, КИП)", "Контроллер с NPU, дуговая защита"],
    ["Магистральный BMS Gateway", "~8 500 узлов", "0,4 – 0,85 млн ₽", "До 30% чека (шкафы, модульные ВА)", "Шлюзы BACnet IP, сторонние счетчики"],
    ["Шкафы насосных и ИТП", "~24 000 шкафов", "0,35 – 0,9 млн ₽", "До 45% чека (OptiMat, ЧРП, шкафы)", "Макросы каскада насосов в ПО"],
    ["Шкафы PDU / мониторинг ЦОД", "~4 500 шкафов", "0,8 – 1,9 млн ₽", "До 40% чека (OptiMat A, АВР, OptiMer)", "Специализированные датчики стоек"]
]
for row_idx, row_data in enumerate(data_gap):
    for col_idx, text in enumerate(row_data):
        cell = t10.cell(row_idx + 1, col_idx)
        cell.fill.solid()
        cell.fill.fore_color.rgb = COLOR_WHITE if row_idx % 2 == 0 else COLOR_GRAY_BG
        p = cell.text_frame.paragraphs[0]
        p.text = text
        p.font.name = 'Arial'
        p.font.size = Pt(9)
        p.font.color.rgb = COLOR_DARK

create_card(s10, 0.8, 5.2, 11.733, 1.4, "Стратегический вывод", [
    "ПЛК занимает 14–25% чека решения, но контролирует спецификацию всего шкафа. Выпуск OptiSmart U/AI переводит КЭАЗ из роли субпоставщика выключателей в позицию генерального поставщика комплексного решения."
], is_accent=True)

# ==================== СЛАЙД 11. ПП РФ 719 ====================
s11 = prs.slides.add_slide(blank_layout)
add_header_and_footer(s11, "Регуляторный барьер: вхождение в реестр ПП РФ № 719 (ПАК)", "Балльная система Минпромторга и приоритизация рыночных сегментов", 11)
create_card(s11, 0.8, 1.6, 3.7, 4.8, "Балльная модель (ПП 719)", [
    "Carrier Board: трассировка и поверхностный монтаж в РФ (партнер «Восток») — 30 баллов.",
    "Корпус: использование серийного корпуса КЭАЗ OptiLogic L — 15 баллов.",
    "Отечественный софт: ПО Gauss 2.0 в реестре Минцифры — 35 баллов.",
    "Итог: >75 баллов (статус отечественного ПАК подтвержден)."
])
create_card(s11, 4.8, 1.6, 3.7, 4.8, "Статус конкурентов", [
    "Wiren Board: не имеет статуса ПАК по ПП 719. Доступ в закупки госкомпаний заблокирован.",
    "Fastwel / Регул: присутствуют в реестре, но ориентированы на тяжелый промышленный сектор (цена кратно выше).",
    "КЭАЗ: занимает открытую нишу доступного отечественного ПАК для массового сегмента НКУ и инфраструктуры."
], is_accent=True)
create_card(s11, 8.8, 1.6, 3.7, 4.8, "Приоритеты продаж", [
    "1. Энергетика и ТЭК (Россети, Газпром) — жесткое требование ПП 719 (+35% к объемам).",
    "2. Объекты КИИ и ЦОД госсектора — обязательность отечественного ПАК.",
    "3. Коммерческая недвижимость — ценовой фактор и комплексность поставки КЭАЗ."
], is_dark=True)

# ==================== СЛАЙД 12. СТРАТЕГИЯ ПО ====================
s12 = prs.slides.add_slide(blank_layout)
add_header_and_footer(s12, "Программный стек: баланс Gauss 2.0 и требования CODESYS", "Экономика лицензирования и двухэтапный софтверный план", 12)
create_card(s12, 0.8, 1.6, 5.7, 4.8, "Базовый рантайм: Gauss 2.0 / SEVON SS", [
    "Стоимость первичной адаптации: всего 300 тыс. руб.",
    "Низкая стоимость лицензии: ~3 350 руб. за 1000 тегов (против 10–15 тыс. руб. у аналогов).",
    "Включение в реестр отечественного софта Минцифры РФ.",
    "Встроенная Web-консоль мнемосхемы щита для обслуживания электриком со смартфона/ПК без SCADA.",
    "Оптимален для 80% задач распределительных шкафов НКУ и технического энергомониторинга."
], is_accent=True)
create_card(s12, 6.8, 1.6, 5.7, 4.8, "Преодоление барьера CODESYS в ТЗ", [
    "Проблема рынка: в проектах ЦОД, водоканалов и крупных насосных станций ТЗ требует CODESYS.",
    "Этап 1 (2027 г.): вывод OptiSmart U с Gauss 2.0 на рынок НКУ, энергоучета и BMS-шлюзов.",
    "Этап 2 (2028 г.): выпуск сертифицированной сборки с ядром Astra IDE (CODESYS-совместимая среда) либо MasterSCADA 4D Runtime.",
    "Результат: удовлетворение 100% проектных спецификаций без переплаты за лицензии в массовых щитах."
], is_dark=True)

# ==================== СЛАЙД 13. БЮДЖЕТ И ФИНМОДЕЛЬ ====================
s13 = prs.slides.add_slide(blank_layout)
add_header_and_footer(s13, "Инвестиционный бюджет CAPEX и финансовый план до 2031 г.", "Детализация R&D затрат и финансовая отдача проекта", 13)
create_card(s13, 0.8, 1.6, 5.2, 4.8, "Структура инвестиций (CAPEX: 7,0 млн ₽)", [
    "Hardware R&D: схемотехника платы под SoM RK3568, тепловое моделирование — 4,0 млн руб.",
    "Оснастка корпуса: 0 руб. (используется готовый корпус OptiLogic L CPU-3, экономия 2,4 млн руб.).",
    "Адаптация ПО Gauss 2.0: портирование рантайма — 0,3 млн руб.",
    "Сертификация: испытания ТР ТС 004/2011 и 020/2011 — 1,2 млн руб.",
    "Пресейл и маркетинг: демо-чемоданы СЩО, САПР-базы — 1,5 млн руб."
])
create_card(s13, 6.3, 1.6, 6.2, 4.8, "Финансовые показатели (2027–2031 гг.)", [
    "Продажи ПЛК: 2027 — 3,9 млн | 2028 — 28,0 млн | 2029 — 48,9 млн | 2030 — 88,0 млн | 2031 — 112,0 млн руб.",
    "Эффективная рентабельность направления: 23,7% – 25,0%.",
    "Присоединенные продажи силовой аппаратуры КЭАЗ: к 2031 г. достигнут 448 млн руб./год.",
    "Срок окупаемости CAPEX: 52 месяца (только ПЛК) и менее 18 месяцев (с учетом маржи комплектного оборудования)."
], is_accent=True)

# ==================== СЛАЙД 14. STAGE-GATE ====================
s14 = prs.slides.add_slide(blank_layout)
add_header_and_footer(s14, "Система контроля рисков Stage-Gate и финальное решение", "Контрольные точки инвестирования и резолюция для совета директоров", 14)
create_card(s14, 0.8, 1.6, 2.7, 4.8, "Gate 1 (Q1-2027)", [
    "Стендовые тесты платы SoM.",
    "Критерий: перегрев CPU не более нормы при +60 °C в закрытом DIN-корпусе.",
    "Транш: подтверждение 4,0 млн руб."
])
create_card(s14, 3.8, 1.6, 2.7, 4.8, "Gate 2 (Q2-2027)", [
    "Сборка софта и шины I/O.",
    "Критерий: устойчивая работа рантайма Gauss 2.0 с модулями OptiLogic L.",
    "Транш: адаптация ПО 0,3 млн руб."
])
create_card(s14, 6.8, 1.6, 2.7, 4.8, "Gate 3 (Q3-2027)", [
    "Сертификация и пилоты.",
    "Критерий: получение протоколов ТР ТС 004/020 и пилотные тесты в СЩО.",
    "Транш: сертификация 1,2 млн руб."
], is_accent=True)
create_card(s14, 9.8, 1.6, 2.7, 4.8, "Решение совета", [
    "1. Одобрить проект разработки OptiSmart U/AI на RK3568.",
    "2. Утвердить бюджет 7,0 млн руб. с поэтапным контролем по Gate 1–3.",
    "3. Выпуск серии — Q4 2027."
], is_dark=True)

# Сохранение презентации
prs.save("OptiSmart_Strategy_Final.pptx")
print("Файл OptiSmart_Strategy_Final.pptx успешно сформирован.")