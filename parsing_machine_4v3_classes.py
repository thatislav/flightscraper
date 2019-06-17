"""
This module parse information about flight tickets from http://www.flybulgarien.dk/en/
with parameters taken from user
"""
from datetime import datetime, timedelta
import re
import sys
from json.decoder import JSONDecodeError
import requests
from lxml import html
from lxml.etree import ParseError, ParserError
from texttable import Texttable


class FlightSearch:
    """Class for taking user's flight parameters,
    checking it and provide filtered information about flights."""
    def __init__(self):
        # словарь с основными данными
        self.data = {'URL': 'http://www.flybulgarien.dk/'}
        # список (словарей) релевантных вылетов ТУДА
        self.departure_list_relevant = []
        # список (словарей) релевантных вылетов ОБРАТНО
        self.arrival_list_relevant = []

    @staticmethod
    def get_city_with_regex(city, search=True):
        """Pulls city-code or codes with regex"""
        regex = re.compile(r'[A-Z]{3}')
        if search:
            return regex.search(city).group()
        return set(regex.findall(city))

    def get_html_from_url(self, url, get=True, params=None, data=None, headers=None):
        """Makes get or post request to url. Returns html-response"""
        exception_flag = False
        try:
            if get:
                response = requests.get(url, params=params, timeout=120)
            else:
                response = requests.post(url, data=data, headers=headers, timeout=120)
            if str(response.status_code) == '200':
                return response
            print('Что-то с ответом с сайта... Попробуйте позже')
        except ConnectionError:
            print('Что-то с соединением...')
            exception_flag = True
        except TimeoutError:
            print('Вышло время ожидания ответа от сайта...')
            exception_flag = True
        finally:
            if exception_flag:
                decision = input('Нажмите "Enter", если хотите попробовать снова\n')
                self.get_cities_from_user() if not decision else sys.exit()

    @staticmethod
    def get_parsed_info(response):
        """Parses html and returns single document"""
        try:
            parsed = html.fromstring(response.text)
        except (ParserError, ParseError):
            print('Что-то с парсингом html-страницы... Обратитесь к администратору программы')
            sys.exit()
        else:
            return parsed

    def get_dep_cities(self):
        """Collects from site all available departure cities"""
        get_request = self.get_html_from_url('{[URL]}en/'.format(self.data))
        parsed = self.get_parsed_info(get_request)
        cities_from_html = parsed.xpath('//*[@id="departure-city"]/option[@value]/text()')
        cities_for_dep = [self.get_city_with_regex(city) for city in cities_from_html]
        self.data['cities_for_dep'] = cities_for_dep

    def checking_user_dep_city(self, city_from_user):
        """Checks if user's dep city is in available dep-cities"""
        while city_from_user.upper() not in self.data['cities_for_dep']:
            city_from_user = input('Введите код города из списка:'
                                   '\n{0[cities_for_dep]}\n'.format(self.data))
        self.data['dep_city'] = city_from_user.upper()

    def get_arr_cities(self):
        """Checks where could to fly from chosen dep_city"""
        get_request = self.get_html_from_url('{0[URL]}script/getcity/2-{0[dep_city]}'.
                                             format(self.data))
        # cities_for_arr = set(self.get_city_with_regex(get_request.text, search=False))
        try:
            cities_for_arr = [city for city in get_request.json()]
        except (JSONDecodeError, UnicodeDecodeError):
            print('Something wrong with json-answer in available arr cities')
            sys.exit()
        else:
            return cities_for_arr

    def get_cities_from_user(self, city_from_user='plug'):
        """Checks for input accuracy of departure city"""
        if 'cities_for_dep' not in self.data:
            self.get_dep_cities()
        self.checking_user_dep_city(city_from_user)
        cities_for_arr = self.get_arr_cities()
        if not cities_for_arr:
            print('..самолёты из {[dep_city]}, к сожалению, никуда не летают..'.format(self.data))
            self.data['cities_for_dep'].remove(self.data['dep_city'])
            self.get_cities_from_user(input('введите другой город: \n'))
        else:
            text = ' или '.join(cities_for_arr)
            print('\nПрекрасно! Самолётом из {0[dep_city]} можно добраться до {1}. '
                  .format(self.data, text))
            if len(cities_for_arr) == 1:
                available_cities = self.data['cities_for_dep'][:]
                available_cities.remove(self.data['dep_city'])
                another_city = input('Если летим туда, нажмите Enter.\n'
                                     '\nИначе выберите другой город из списка:\n{}\n'.
                                     format(available_cities))
                if not another_city:
                    self.data['arr_city'] = text.upper()
                    print('* город прибытия - {[arr_city]}'.format(self.data))
                else:
                    self.get_cities_from_user(another_city)
            else:
                city_from_user = input('\n* город прибытия:\n')
                while not city_from_user.upper() in cities_for_arr:
                    print(text)
                    city_from_user = input('\n* город прибытия: \n')
                self.data['arr_city'] = city_from_user.upper()

    def available_dates(self, for_depart=True):
        """Pulls out available dates"""
        if for_depart:  # Runs scenario for getting dates for departure
            if 'dates_for_dep' not in self.data.keys():
                body = 'code1={0[dep_city]}&code2={0[arr_city]}'.format(self.data)
                headers = {'Content-Type': 'application/x-www-form-urlencoded'}
                # make post_request to site with selected cities, to know available dates
                post_request = self.get_html_from_url('{[URL]}script/getdates/2-departure'.
                                                      format(self.data),
                                                      get=False, data=body, headers=headers)
                raw_dates_from_html = set(re.findall(r'(\d{4},\d{1,2},\d{1,2})', post_request.text))
                dates_for_dep = \
                    [datetime.strptime(raw_date, '%Y,%m,%d') for raw_date in raw_dates_from_html]
                self.data['dates_for_dep'] = sorted(dates_for_dep)
            return self.data['dates_for_dep']
        # Runs scenario for getting dates for arrive
        # Arrival dates coming from site are the same as departure dates
        self.data['dates_for_arr'] = \
            [date for date in self.data['dates_for_dep'] if date >= self.data['dep_date']]
        return self.data['dates_for_arr']

    def get_date_in_format(self, date_from_user):
        """Checks for date input accuracy, and convert date into Datetime format"""
        try:
            return datetime.strptime(date_from_user, '%d.%m.%Y')
        except ValueError:
            return self.get_date_in_format(input(
                'Дата введена некорректно. Формат даты: "ДД.ММ.ГГГГ". Повторите ввод:\n'))

    @staticmethod
    def get_ddmmyyyy_from_datetime(date):
        """Converts datetime to dd.mm.yyyy str-format"""
        return datetime.strftime(date, '%d.%m.%Y')

    def check_dep_date(self, date_from_user):
        """Checks if user's date suitable for choice for departure date"""
        verified_dep_date = self.get_date_in_format(date_from_user)
        dates_for_dep = self.available_dates()
        if verified_dep_date not in dates_for_dep:
            self.check_dep_date(input(
                ' - для выбора доступна любая из этих дат:\n{}\nКакую выберЕте?\n'.
                format([self.get_ddmmyyyy_from_datetime(date) for date in dates_for_dep])))
        else:
            self.data['dep_date'] = verified_dep_date
            self.data['dep_date_for_url'] = self.get_ddmmyyyy_from_datetime(self.data['dep_date'])
            print('\nСупер! Почти всё готово. Обратный билет будем брать?'
                  '\nЕсли да - введите дату, если нет - нажмите Enter')

    def check_arr_date(self, date_from_user):
        """Checks for the presence of the input of arrival date"""
        if not date_from_user:
            print('Ок! One-way ticket!\nИтак, что мы имеем...')
            print('\n===============..Минутчку, пожалст..====================')
            self.data['arr_date_for_url'] = None
            self.data['ow'] = ''
        else:
            verified_arr_date = self.get_date_in_format(date_from_user)
            dates_for_arr = self.available_dates(for_depart=False)
            if verified_arr_date not in dates_for_arr:
                self.check_arr_date(input(
                    ' - выберите любую из этих дат:\n{}\n'.
                    format([self.get_ddmmyyyy_from_datetime(date) for date in dates_for_arr])))
            else:
                self.data['arr_date'] = verified_arr_date
                print('\n===============..Минутчку, пожалст..====================')
                self.data['arr_date_for_url'] = \
                    self.get_ddmmyyyy_from_datetime(self.data['arr_date'])
                self.data['rt'] = ''

    def prepare_finishing_flight_info(self, flight):
        """Checks if flight data getting from site is suitable for user's parameters"""
        finished_flight_info = \
            {'from': self.get_city_with_regex(flight[3]),
             'to': self.get_city_with_regex(flight[4]),
             'price': float(flight[5].split()[1]),
             'currency': flight[5].split()[2]}
        # время взлета в формате datetime
        finished_flight_info['dep_time'] = \
            datetime.strptime(flight[0] + ' ' + flight[1], '%a, %d %b %y %H:%M')
        # время посадки в формате datetime
        finished_flight_info['arr_time'] = \
            datetime.strptime(flight[0] + ' ' + flight[2], '%a, %d %b %y %H:%M')
        # к дате посадки +1 день, если время взлёта позднее времени посадки
        if finished_flight_info['dep_time'] > finished_flight_info['arr_time']:
            finished_flight_info['arr_time'] += timedelta(days=1)
        finished_flight_info['duration'] = \
            finished_flight_info['arr_time'] - finished_flight_info['dep_time']
        return finished_flight_info

    def check_site_info(self, flight_info, price_info, relevant_list, all_list,
                        return_flight=False):
        """Gets one of two lists:
        1) flights suitable for user's flight parameters - relevant_list
        2) all flights offered by site - all_list"""
        # готовим параметры в соответствии с тем,
        # используется функция для вылета ТУДА (return_flight=False)
        # или ОБРАТНО (return_flight=True)
        dep_city = lambda return_flight: self.data['arr_city'] \
            if return_flight else self.data['dep_city']
        arr_city = lambda return_flight: self.data['dep_city'] \
            if return_flight else self.data['arr_city']
        dep_date = lambda return_flight: self.data['arr_date'] \
            if return_flight else self.data['dep_date']

        prepared_flights_info = []
        # приводим данные в удобный для дальнейшей обработки вид и
        # наполняем ими список prepared_flights_info
        for i, flight_variant in enumerate(zip(flight_info, price_info)):
            prepared_flights_info.append([])
            for element in flight_variant:
                for piece in element.xpath('./td/text()'):
                    prepared_flights_info[i].append(piece)
        for flight in prepared_flights_info:
            # если вылет подходит под запрос юзера,
            # сохраняем его в соотв-щий список relevant_list
            if (self.get_city_with_regex(flight[3]) == dep_city(return_flight))\
                    and (self.get_city_with_regex(flight[4]) == arr_city(return_flight))\
                    and (datetime.strptime(flight[0], '%a, %d %b %y') == dep_date(return_flight)):
                relevant_list.append(self.prepare_finishing_flight_info(flight))
            # если вылет не подходит под запрос юзера,
            # тоже сохраняем его, но уже в список всех вылетов all_list
            else:
                all_list.append(self.prepare_finishing_flight_info(flight))

    @staticmethod
    def print_flights_table(flights_list, header):
        """Prints flight information in beautiful way"""
        table_for_suitable_flights = Texttable(max_width=100)
        table_for_suitable_flights.header(header)
        table_for_suitable_flights.add_rows(flights_list, header=False)
        print(table_for_suitable_flights.draw())

    @staticmethod
    def get_hhmm_ddmmyyyy_from_datetime(date):
        """Converts datetime in HH:MM dd.mm.yyyy str-format"""
        return datetime.strftime(date, '%H:%M %d.%m.%Y')

    def show_suitable_flights(self, list_relevant, list_all, return_flight=False):
        """Checks if there are list with relevant flights or list with all offered flights
        and prepares it to print."""
        # если подходящие вылеты были, выводим их на экран
        list_filtered = list()
        # готовим параметры в соответствии с тем,
        # используется функция для вылета ТУДА (return_flight=False)
        # или ОБРАТНО (return_flight=True)
        dep_city = lambda return_flight: self.data['arr_city'] \
            if return_flight else self.data['dep_city']
        arr_city = lambda return_flight: self.data['dep_city'] \
            if return_flight else self.data['arr_city']
        if list_relevant:
            print('\nДля маршрута из {0} в {1} нашлось следующее:'.
                  format(dep_city(return_flight), arr_city(return_flight)))
            header = 'Взлёт в:\tПосадка в:\tДлительность перелёта:\tЦена билета:'.split('\t')
            for flight in list_relevant:
                flight_restruct = [self.get_hhmm_ddmmyyyy_from_datetime(flight['dep_time']),
                                   self.get_hhmm_ddmmyyyy_from_datetime(flight['arr_time']),
                                   flight['arr_time'] - flight['dep_time'],
                                   str(flight['price']) + ' ' + flight['currency']]
                list_filtered.append(flight_restruct)
            self.print_flights_table(list_filtered, header)
        # иначе выводим сообщение, что подходящих вылетов нет,
        # и на всякий выдаём инфу о всех предложенных сайтом вылетах
        else:
            print('\nК сожалению, вылетов из {0} в {1} на указанную дату не нашлось.'
                  '\nНо это только пока, не отчаивайтесь ;)'
                  .format(dep_city(return_flight), arr_city(return_flight)))
            if list_all:
                print('\nЗато есть вот такие варианты:\n')
                header = \
                    'Откуда:\tВзлёт в:\tКуда:\tПосадка в:\tДлительность перелёта:\tЦена билета:'.\
                    split('\t')
                for flight in list_all:
                    flight_restruct = [flight['from'],
                                       self.get_hhmm_ddmmyyyy_from_datetime(flight['dep_time']),
                                       flight['to'],
                                       self.get_hhmm_ddmmyyyy_from_datetime(flight['arr_time']),
                                       flight['arr_time'] - flight['dep_time'],
                                       str(flight['price']) + ' ' + flight['currency']]
                    list_filtered.append(flight_restruct)
                self.print_flights_table(list_filtered, header)

    def find_and_show_flights(self):
        """Runs general flight information gathering and print it"""
        url = 'https://apps.penguin.bg/fly/quote3.aspx'
        payload = {'ow': self.data.get('ow'),
                   'rt': self.data.get('rt'),
                   'lang': 'en',
                   'depdate': self.data.get('dep_date_for_url'),
                   'aptcode1': self.data.get('dep_city'),
                   'rtdate': self.data.get('arr_date_for_url'),
                   'aptcode2': self.data['arr_city'],
                   'paxcount': 1,
                   'infcount': ''}
        r_final = self.get_html_from_url(url, params=payload)
        tree = self.get_parsed_info(r_final)
        info_dep = tree.xpath('//tr[starts-with(@id, "flywiz_rinf")]')
        price_dep = tree.xpath('//tr[starts-with(@id, "flywiz_rprc")]')
        info_arr = tree.xpath('//tr[starts-with(@id, "flywiz_irinf")]')
        price_arr = tree.xpath('//tr[starts-with(@id, "flywiz_irprc")]')
        # список (словарей) всех вылетов ТУДА, выданных сайтом
        departure_list_all = []
        # список (словарей) релевантных вылетов ОБРАТНО
        arrival_list_all = []
        self.check_site_info(info_dep, price_dep, self.departure_list_relevant, departure_list_all)
        self.show_suitable_flights(self.departure_list_relevant, departure_list_all)
        if 'arr_date' in self.data.keys():
            self.check_site_info(info_arr, price_arr, self.arrival_list_relevant, arrival_list_all,
                                 return_flight=True)
            self.show_suitable_flights(self.arrival_list_relevant, arrival_list_all,
                                       return_flight=True)

    def final_checking(self):
        """Calculates all available variants of back and forth flights if there are,
        sorts them by total price and prints."""
        if self.departure_list_relevant and self.arrival_list_relevant:
            print('\n' + (36 * '=') + ' ИТОГО ' + (36 * '=') + '\n')
            flight_list_of_dicts = []
            for dep_flight in self.departure_list_relevant:
                for arr_flight in self.arrival_list_relevant:
                    if dep_flight['arr_time'] > arr_flight['dep_time']:
                        print('После посадки в {0[arr_city]} в {1} '
                              'обратным рейсом в {2} улететь уже невозможно.'.
                              format(self.data,
                                     self.get_hhmm_ddmmyyyy_from_datetime(dep_flight['arr_time']),
                                     self.get_hhmm_ddmmyyyy_from_datetime(arr_flight['dep_time'])))
                        continue
                    flight_dict = dict()
                    flight_dict['dep_time_to'] = self.get_hhmm_ddmmyyyy_from_datetime(
                        dep_flight['dep_time'])
                    flight_dict['dep_time_from'] = \
                        self.get_hhmm_ddmmyyyy_from_datetime(arr_flight['dep_time'])
                    flight_dict['duration'] = \
                        (dep_flight['arr_time'] - dep_flight['dep_time']) \
                        + (arr_flight['arr_time'] - arr_flight['dep_time'])
                    flight_dict['full_price'] = \
                        str(dep_flight['price'] + arr_flight['price']) + ' ' + dep_flight[
                            'currency']
                    flight_list_of_dicts.append(flight_dict)
            if flight_list_of_dicts:
                sorted_flight_list_of_dicts = \
                    sorted(flight_list_of_dicts, key=lambda k: k['full_price'])
                sorted_flight_list_of_lists = \
                    [[v for v in flight_d.values()] for flight_d in sorted_flight_list_of_dicts]
                header = \
                    'Из {0[dep_city]} в {0[arr_city]}:\t' \
                    'Назад:\t' \
                    'Итого в полёте(ЧЧ:ММ):\t' \
                    'Итого цена:'\
                    .format(self.data).split('\t')
                self.print_flights_table(sorted_flight_list_of_lists, header)

    def start(self):
        """Main method that runs others."""
        self.get_cities_from_user()
        self.check_dep_date(input('\n* дата вылета (ДД.ММ.ГГГГ):\n'))
        self.check_arr_date(input('\n* дата возврата (необязательно) (ДД.ММ.ГГГГ):\n'))
        self.find_and_show_flights()
        self.final_checking()
        if self.departure_list_relevant:
            print('\nСчастливого пути! :)')
        else:
            print('\nКто ищет, тот всегда найдёт! :)')


if __name__ == '__main__':

    print('\nСалют! Билеты на самолёт??\nПроще простого!\n')
    CHECKER = FlightSearch()
    CHECKER.start()