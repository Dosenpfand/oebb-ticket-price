import requests
from datetime import datetime
import time


def get_access_token():
    r = requests.get('https://tickets-mobile.oebb.at/api/domain/v4/init')
    access_token = r.json().get('accessToken')
    return access_token


def get_request_headers(access_token=None):
    if not access_token:
        access_token = get_access_token()

        if not access_token:
            return None

    headers = {'AccessToken': access_token}
    return headers


def get_station_id(name, access_token=None):
    headers = get_request_headers(access_token)
    params = {'name': name, 'count': 1}
    r = requests.get('https://tickets.oebb.at/api/hafas/v1/stations', params, headers=headers)
    if not type(r.json()) is list:
        return None
    return r.json()[0]['number']


def get_travel_action_id(origin_id, destination_id, date=None, access_token=None):
    if not date:
        date = datetime.now()
    headers = get_request_headers(access_token)

    url = 'https://tickets.oebb.at/api/offer/v2/travelActions'
    data = {'from':
    # TODO: lat,long not needed, name not relevant
        {
            # 'latitude': 48208548, 'longitude': 16372132,
            'name': 'Wien',
            'number': origin_id
        },
        'to':
            {
                # 'latitude': 47263774, 'longitude': 11400973,
                'name': 'Innsbruck',
                'number': destination_id},
        'datetime': date.isoformat(), 'customerVias': [], 'ignoreHistory': True,
        'filter':
            {'productTypes': [], 'history': True, 'maxEntries': 5, 'channel': 'inet'}
    }

    r = requests.post(url, json=data, headers=headers)

    travel_actions = r.json().get('travelActions')
    if not travel_actions:
        return None

    travel_action = next(action for action in travel_actions if action['type'] == 'timetable')
    if not travel_action:
        return None

    travel_action_id = travel_action['id']
    return travel_action_id


def get_connection_id(travel_action_id, date=None, has_vc66=False, access_token=None):
    url = 'https://tickets.oebb.at/api/hafas/v4/timetable'
    if not date:
        date = datetime.now()

    cards = []
    if has_vc66:
        cards.append(
            {
                "name": "Vorteilscard 66",
                "cardId": 9097862,
                "numberRequired": False,
                "isChallenged": False,
                "isFamily": False,
                "isSelectable": True,
                "image": "discountCard",
                "isMergeableIntoCustomerAccount": True,
                "motorailTrainRelevance": "PERSON_ONLY"
            }
        )
    data = {'travelActionId': travel_action_id, 'datetimeDeparture': date.isoformat(),
            'filter':
                {'regionaltrains': False, 'direct': False, 'wheelchair': False, 'bikes': False, 'trains': False,
                 'motorail': False, 'connections': []},
            'passengers':
                [{'me': False, 'remembered': False, 'markedForDeath': False,
                  'challengedFlags': {'hasHandicappedPass': False, 'hasAssistanceDog': False, 'hasWheelchair': False,
                                      'hasAttendant': False},
                  'cards': cards,
                  'relations': [],
                  'isBirthdateChangeable': True,
                  'isBirthdateDeletable': True, 'isNameChangeable': True, 'isDeletable': True, 'isSelected': True,
                  'id': int(time.time()), 'type': 'ADULT', 'birthdateChangeable': True, 'birthdateDeletable': True,
                  'nameChangeable': True, 'passengerDeletable': True}],
            'entryPointId': 'timetable', 'count': 5,
            'debugFilter':
                {'noAggregationFilter': False, 'noEqclassFilter': False, 'noNrtpathFilter': False,
                 'noPaymentFilter': False, 'useTripartFilter': False, 'noVbxFilter': False,
                 'noCategoriesFilter': False},
            'sortType': 'DEPARTURE', }
    # TODO: not necessary?
    # 'from': {'latitude': 48208548, 'longitude': 16372132, 'name': 'Wien', 'number': 1190100},
    # 'to': {'latitude': 47263774, 'longitude': 11400973, 'name': 'Innsbruck', 'number': 1170101}}
    headers = get_request_headers(access_token)
    r = requests.post(url, json=data, headers=headers)
    if not r.json().get('connections') or not type(r.json()['connections']) is list:
        return None

    connection_id = r.json()['connections'][0]['id']
    return connection_id


def get_price_for_connection(connection_id, access_token=None):
    url = 'https://tickets.oebb.at/api/offer/v1/prices'
    params = {'connectionIds[]': connection_id, 'sortType': 'DEPARTURE', 'bestPriceId': 'undefined'}
    headers = get_request_headers(access_token)
    r = requests.get(url, params, headers=headers)
    return r.json()['offers'][0].get('price')


def get_price(origin, destination, date=None, has_vc66=False, access_token=None):
    # TODO: support for "Ticket für Teilstrecke"
    # TODO: do not only take first but average/median over multiple?
    if not access_token:
        access_token = get_access_token()
    if not access_token:
        return None

    origin_id = get_station_id(origin, access_token=access_token)
    destination_id = get_station_id(destination, access_token=access_token)
    if not origin_id or not destination_id:
        return None

    travel_action_id = get_travel_action_id(origin_id, destination_id, date=date, access_token=access_token)
    connection_id = get_connection_id(travel_action_id, date=date, has_vc66=has_vc66, access_token=access_token)
    if not connection_id:
        return None

    price = get_price_for_connection(connection_id, access_token=access_token)
    return price


def get_price_generator(origin, destination, date=None, has_vc66=False, access_token=None):
    if not access_token:
        yield 'event: UpdateEvent\ndata: Generating access token\n\n'
        access_token = get_access_token()
        if not access_token:
            yield 'event: UpdateEvent\ndata: Failed to generate access token\n\n'
            return

    yield 'event: UpdateEvent\ndata: Processing origin\n\n'
    origin_id = get_station_id(origin, access_token=access_token)
    if not origin_id:
        yield 'event: UpdateEvent\ndata: Failed to process origin\n\n'
        return

    yield 'event: UpdateEvent\ndata: Processing destination\n\n'
    destination_id = get_station_id(destination, access_token=access_token)
    if not destination_id:
        yield 'event: UpdateEvent\ndata: Failed to process destination\n\n'
        return

    yield 'event: UpdateEvent\ndata: Processing travel action\n\n'
    travel_action_id = get_travel_action_id(origin_id, destination_id, date=date, access_token=access_token)
    if not travel_action_id:
        yield 'event: UpdateEvent\ndata: Failed to process travel action\n\n'
        return

    yield 'event: UpdateEvent\ndata: Processing connection\n\n'
    connection_id = get_connection_id(travel_action_id, date=date, has_vc66=has_vc66, access_token=access_token)
    if not connection_id:
        yield 'event: UpdateEvent\ndata: Failed to process connection\n\n'
        return

    yield f'event: UpdateEvent\ndata: Retrieving price\n\n'
    price = get_price_for_connection(connection_id, access_token=access_token)
    if not price:
        yield 'event: UpdateEvent\ndata: Failed to retrieve price\n\n'
        return

    yield f'event: UpdateEvent\ndata: Price for a ticket from {origin} to {destination}: <b>{price} €</b>\n\n'


# TODO: delete
if __name__ == '__main__':
    print(get_price('Wien', 'Bozen'))
    print(get_price('Wien', 'Bozen', has_vc66=True))
