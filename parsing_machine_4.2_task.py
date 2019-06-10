"""
This module parse information about flight tickets from http://www.flybulgarien.dk/en/
with parameters taken from user
"""
from datetime import datetime, timedelta
import re
import requests
from lxml import html
from texttable import Texttable


DATA = {'URL': 'http://www.flybulgarien.dk/'}


def get_city_with_regex(city):
    return re.search('[A-Z]{3}', city).group()


def get_cities_from_user(city_from_user):
    """Check for input accuracy of departure city"""
    response = requests.get('{[URL]}en/'.format(DATA))
    parsed = html.fromstring(response.text)
    cities_from_html = parsed.xpath('//*[@id="departure-city"]/option[@value]/text()')
    cities_for_dep = [get_city_with_regex(city) for city in cities_from_html]
    while city_from_user.upper() not in cities_for_dep:
        city_from_user = input(
            ' - город введён неверно. Введите код города из списка: {}\n'.format(cities_for_dep))
    DATA['dep_city'] = city_from_user.upper()
    r_new = requests.get('{0[URL]}script/getcity/2-{0[dep_city]}'.
                         format(DATA))
    cities_for_arr = [city for city in r_new.json()]
    if not cities_for_arr:
        print('..самолёты из {[dep_city]}, к сожалению, никуда не летают..'.
              format(DATA))
        get_cities_from_user(input('введите другой город: \n'))
    elif len(cities_for_arr) == 1:
        DATA['arr_city'] = cities_for_arr[0]
        print('\nПрекрасно! Самолётом из {0[dep_city]} можно добраться только до {0[arr_city]}.'
              '\n* город прибытия: {0[arr_city]}'.
              format(DATA))
        # check_arr_city(DATA['arr_city'])
    else:
        text = ' или '.join(cities_for_arr)
        print('\nПрекрасно! Самолётом из {0[dep_city]} можно добраться до {1}. Куда направляетесь?'.
              format(DATA, text))
        city_from_user = input('\n* город прибытия:\n')
        while not city_from_user.upper() in cities_for_arr:
            print(text)
            city_from_user = input('\n* город прибытия: \n')
        DATA['arr_city'] = city_from_user.upper()


def get_datetime_from_str(string):
    try:
        return datetime.strptime(string, '%a, %d %b %y %H:%M')
    except ValueError:
        try:
            return datetime.strptime(string, '%a, %d %b %y')
        except ValueError:
            return datetime.strptime(string, '%Y,%m,%d')


def available_dates(for_depart=True):
    """Pull out available dates"""
    if for_depart:  # Runs scenario for getting dates for departure
        if 'dates_for_dep' not in DATA.keys():
            body = 'code1={0[dep_city]}&code2={0[arr_city]}'.format(DATA)
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            # make POST-request to site with selected cities, to know available dates
            r_new = requests.post('{[URL]}script/getdates/2-departure'.format(DATA),
                                  data=body, headers=headers)
            raw_dates_from_html = set(re.findall(r'(\d{4},\d{1,2},\d{1,2})', r_new.text))
            dates_for_dep = [get_datetime_from_str(raw_date) for raw_date in raw_dates_from_html]
            DATA['dates_for_dep'] = sorted(dates_for_dep)
        return DATA['dates_for_dep']
    # Runs scenario for getting dates for arrive
    DATA['dates_for_arr'] = [date for date in DATA['dates_for_dep'] if date >= DATA['dep_date']]
    return DATA['dates_for_arr']


def get_date_in_format(date_from_user):
    """Check for date input accuracy, and convert date into Datetime format"""
    try:
        return datetime.strptime(date_from_user, '%d.%m.%Y')
    except ValueError:
        return get_date_in_format(input(
            'Дата введена некорректно. Формат даты: "ДД.ММ.ГГГГ". Повторите ввод:\n'))


def get_ddmmyyyy_from_datetime(date):
    return datetime.strftime(date, '%d.%m.%Y')


def check_dep_date(date_from_user):
    """Check if user's date suitable for choice for departure date"""
    verified_dep_date = get_date_in_format(date_from_user)
    dates_for_dep = available_dates()
    if verified_dep_date not in dates_for_dep:
        check_dep_date(input(
            ' - для выбора доступна любая из этих дат:\n{}\nКакую выберЕте?\n'.
                format([get_ddmmyyyy_from_datetime(date) for date in dates_for_dep]))
        )
    else:
        DATA['dep_date'] = verified_dep_date
        DATA['dep_date_for_url'] = get_ddmmyyyy_from_datetime(DATA['dep_date'])
        print('\nСупер! Почти всё готово. Обратный билет будем брать?'
              '\nЕсли да - введите дату, если нет - нажмите Enter')


def check_arr_date(date_from_user):
    """Check for the presence of the input of arrival date"""
    if not date_from_user:
        print('Ок! One-way ticket!\nИтак, что мы имеем...')
        check_if_oneway_flight()
    else:
        verified_arr_date = get_date_in_format(date_from_user)
        dates_for_arr = available_dates(for_depart=False)
        if verified_arr_date not in dates_for_arr:
            check_arr_date(input(
                ' - выберите любую из этих дат:\n{}\n'.
                    format([get_ddmmyyyy_from_datetime(date) for date in dates_for_arr])))
        else:
            DATA['arr_date'] = verified_arr_date
            check_if_oneway_flight(one_way=False)


def check_if_oneway_flight(one_way=True):
    """Check return flight"""
    print('\n===============..Минутчку, пожалст..====================')
    if one_way:
        DATA['arr_date_for_url'] = ''
        DATA['flag'] = 'ow'
        # DATA['arr_date'] = ''
    else:
        DATA['arr_date_for_url'] = '&rtdate=' + get_ddmmyyyy_from_datetime(DATA['arr_date'])
        DATA['flag'] = 'rt'


# FIXME Program starts here
print('\nСалют! Билеты на самолёт??\nПроще простого! Введите:\n')
get_cities_from_user(input('* город отправления:\n'))
check_dep_date(input('\n* дата вылета (ДД.ММ.ГГГГ):\n'))
check_arr_date(input('\n* дата возврата (необязательно) (ДД.ММ.ГГГГ):\n'))


R_FINAL = requests.get(
    'https://apps.penguin.bg/fly/quote3.aspx?{0[flag]}=&lang=en&depdate={0[dep_date_for_url]}' \
      '&aptcode1={0[dep_city]}{0[arr_date_for_url]}&aptcode2={0[arr_city]}&paxcount=1&infcount='.\
    format(DATA))
TREE = html.fromstring(R_FINAL.text)
INFO_DEP = TREE.xpath('//tr[starts-with(@id, "flywiz_rinf")]')
PRICE_DEP = TREE.xpath('//tr[starts-with(@id, "flywiz_rprc")]')
INFO_ARR = TREE.xpath('//tr[starts-with(@id, "flywiz_irinf")]')
PRICE_ARR = TREE.xpath('//tr[starts-with(@id, "flywiz_irprc")]')
# список (словарей) релевантных вылетов ТУДА
DEPARTURE_LIST_RELEVANT = []
# список (словарей) всех вылетов ТУДА, выданных сайтом
DEPARTURE_LIST_ALL = []
# список (словарей) релевантных вылетов ОБРАТНО
ARRIVAL_LIST_RELEVANT = []
# список (словарей) всех вылетов ОБРАТНО, выданных сайтом
ARRIVAL_LIST_ALL = []


def change_data_dict():
    """Меняем главный словарь с параметрами от юзера
    для использования при поиске обратного полёта"""
    DATA['dep_city'], DATA['arr_city'] = DATA['arr_city'], DATA['dep_city']
    DATA['dep_date'], DATA['arr_date'] = DATA['arr_date'], DATA['dep_date']


def prepare_finishing_flight_info(flight):
    """Проверяем подходят ли данные о вылете под параметры юзера"""
    finished_flight_info = dict()
    # время взлета в формате datetime
    finished_flight_info['dep_time'] = get_datetime_from_str(flight[0] + ' ' + flight[1])
    # время посадки в формате datetime
    finished_flight_info['arr_time'] = get_datetime_from_str(flight[0] + ' ' + flight[2])
    # к дате посадки +1 день, если время взлёта позднее времени посадки
    if finished_flight_info['dep_time'] > finished_flight_info['arr_time']:
        finished_flight_info['arr_time'] += timedelta(days=1)
    finished_flight_info['duration'] = \
        finished_flight_info['arr_time'] - finished_flight_info['dep_time']
    finished_flight_info['price'] = float(flight[5].split()[1])
    finished_flight_info['currency'] = flight[5].split()[2]
    finished_flight_info['from'] = get_city_with_regex(flight[3])
    finished_flight_info['to'] = get_city_with_regex(flight[4])
    return finished_flight_info


def check_site_info(flight_info, price_info, relevant_list, all_list, return_flight=False):
    """Получаем 1 из 2 списков:
    1) подходящих под параметры вылетов - relevant_list
    2) и всех вылетов, прежложенных сайтом - all_list"""
    # необработанные данные с сайта о вылетах в списке
    prepared_flights_info = []
    i = 0
    # наполняем необрабортанными данными список prepared_flights_info
    for flight_variant in [full_info for full_info in zip(flight_info, price_info)]:
        prepared_flights_info.append([])
        for element in flight_variant:
            for piece in element.xpath('./td/text()'):
                prepared_flights_info[i].append(piece)
        i += 1
    # если функция используется для проверки вылетов в обратном направлении (direction == 2),
    # то правим словарь с параметрами вылета, чтобы по-прежнему можно пользоваться этой функцией
    if return_flight:
        change_data_dict()
    # теперь отбираем из выдачи сайта (prepared_flights_info) -
    # все подходящие под запрос юзера вылеты ТУДА в список словарей site_info_finished
    for flight in prepared_flights_info:
        # если вылет подходит под запрос юзера,
        # сохраняем его в соотв-щий список relevant_list
        if (get_city_with_regex(flight[3]) == DATA['dep_city']) \
                and (get_city_with_regex(flight[4]) == DATA['arr_city'])\
                and (get_datetime_from_str(flight[0]) == DATA['dep_date']):
            relevant_list.append(prepare_finishing_flight_info(flight))
        # если вылет не подходит под запрос юзера,
        # тоже сохраняем его, но уже в список всех вылетов all_list
        else:
            all_list.append(prepare_finishing_flight_info(flight))


def print_flights_table(flights_list, header, list_is_relevant=True):
    table_for_suitable_flights = Texttable(max_width=100)
    table_for_suitable_flights.header(header)
    table_for_suitable_flights.add_rows(flights_list, header=False)
    print(table_for_suitable_flights.draw())


def get_hhmm_ddmmyyyy_from_datetime(date):
    return datetime.strftime(date, '%H:%M %d.%m.%Y')


def show_suitable_flights(list_relevant, list_all, return_flight=False):
    """Проверяем, есть ли подходящие вылеты"""
    # если подходящие вылеты были, выводим их на экран
    list_filtered = list()
    if list_relevant:
        print('\nДля маршрута из {0[dep_city]} в {0[arr_city]} нашлось следующее:'.
              format(DATA))
        header = 'Взлёт в:\tПосадка в:\tДлительность перелёта:\tЦена билета:'.split('\t')
        for flight in list_relevant:
            flight_restruct = [get_hhmm_ddmmyyyy_from_datetime(flight['dep_time']),
                               get_hhmm_ddmmyyyy_from_datetime(flight['arr_time']),
                               flight['arr_time'] - flight['dep_time'],
                               str(flight['price']) + ' ' + flight['currency']]
            list_filtered.append(flight_restruct)
        print_flights_table(list_filtered, header)
    # иначе выводим сообщение, что подходящих вылетов нет,
    # и на всякий выдаём инфу о всех предложенных сайтом вылетах
    else:
        print('\nК сожалению, вылетов из {0[dep_city]} в {0[arr_city]} не нашлось.'
              '\nНо это только пока, не отчаивайтесь ;)'.format(DATA))
        if list_all:
            print('\nЗато есть вот такие варианты:\n')
            header = \
                'Откуда:\tВзлёт в:\tКуда:\tПосадка в:\tДлительность перелёта:\tЦена билета:'.split('\t')
            for flight in list_all:
                flight_restruct = [flight['from'],
                                   get_hhmm_ddmmyyyy_from_datetime(flight['dep_time']),
                                   flight['to'],
                                   get_hhmm_ddmmyyyy_from_datetime(flight['arr_time']),
                                   flight['arr_time'] - flight['dep_time'],
                                   str(flight['price']) + ' ' + flight['currency']]
                list_filtered.append(flight_restruct)
            print_flights_table(list_filtered, header, list_is_relevant=False)


check_site_info(INFO_DEP, PRICE_DEP, DEPARTURE_LIST_RELEVANT, DEPARTURE_LIST_ALL)
show_suitable_flights(DEPARTURE_LIST_RELEVANT, DEPARTURE_LIST_ALL)
if 'arr_date' in DATA.keys():
    check_site_info(INFO_ARR, PRICE_ARR, ARRIVAL_LIST_RELEVANT, ARRIVAL_LIST_ALL,
                    return_flight=True)
    show_suitable_flights(ARRIVAL_LIST_RELEVANT, ARRIVAL_LIST_ALL, return_flight=True)

# если нашлись подходящие вылеты и ТУДА, и ОБРАТНО,
# то считаем все возможные варианты пар ТУДА-ОБРАТНО,
# сортируем по общей стоимости, выводим на экран
if DEPARTURE_LIST_RELEVANT and ARRIVAL_LIST_RELEVANT:
    print('\n' + (36 * '=') + ' ИТОГО ' + (36 * '=') + '\n')
    FLIGHT_LIST_OF_DICTS = []
    for dep_flight in DEPARTURE_LIST_RELEVANT:
        for arr_flight in ARRIVAL_LIST_RELEVANT:
            if dep_flight['arr_time'] > arr_flight['dep_time']:
                print('После посадки в {0[dep_city]} в {1} '
                      'обратным рейсом в {2} улететь уже невозможно.'.
                      format(DATA,
                             get_hhmm_ddmmyyyy_from_datetime(dep_flight['arr_time']),
                             get_hhmm_ddmmyyyy_from_datetime(arr_flight['dep_time'])))
                continue
            flight_dict = dict()
            flight_dict['dep_time_to'] = get_hhmm_ddmmyyyy_from_datetime(dep_flight['dep_time'])
            flight_dict['dep_time_from'] = get_hhmm_ddmmyyyy_from_datetime(arr_flight['dep_time'])
            flight_dict['v_polete'] = \
                (dep_flight['arr_time'] - dep_flight['dep_time']) \
                + (arr_flight['arr_time'] - arr_flight['dep_time'])
            flight_dict['full_price'] = \
                str(dep_flight['price'] + arr_flight['price']) + ' ' + dep_flight['currency']
            FLIGHT_LIST_OF_DICTS.append(flight_dict)
    if FLIGHT_LIST_OF_DICTS:
        SORTED_FLIGHT_LIST_OF_DICTS = sorted(FLIGHT_LIST_OF_DICTS, key=lambda k: k['full_price'])
        SORTED_FLIGHT_LIST_OF_LISTS = \
            [[v for v in flight_d.values()] for flight_d in SORTED_FLIGHT_LIST_OF_DICTS]
        header = 'Из {0[arr_city]} в {0[dep_city]}:\tНазад:\tИтого в полёте(ЧЧ:ММ):\tИтого цена:'.\
            format(DATA).split('\t')
        print_flights_table(SORTED_FLIGHT_LIST_OF_LISTS, header)

# input('\n\n\nWait a minute...\n')
