import requests
import json
import datetime
import hassapi as hass
import homeassistant as hass2

API_BASE_ADDRESS = 'https://curlbus.app'

class BusStop:
    def __init__(self, id: int):
        self.stop_id = id

    def getName(self):
        url = f'{API_BASE_ADDRESS}/{self.stop_id}'
        response = requests.get(url, headers={'accept': 'application/json'})
        jsonStr = response.content
        info = json.loads(jsonStr)
        stop_name = info['stop_info']['name']['HE']
        return stop_name

    def getNextArrivals(self):
        url = f'{API_BASE_ADDRESS}/{self.stop_id}'
        response = requests.get(url, headers={'accept': 'application/json'})
        jsonStr = response.content
        info = json.loads(jsonStr)
        stop_name = info['stop_info']['name']['HE']

        print(f'next arrivals for {stop_name}:')
        for visit in info['visits'][str(self.stop_id)]:
            line_name = visit['line_name']
            line_dest = visit['destination_id']
            dest = BusStop(line_dest)
            dest_name = dest.getName()
            etaStr = visit['eta']
            eta = datetime.datetime.fromisoformat(etaStr).replace(tzinfo=None)
            now = datetime.datetime.now()
            #print(f'line {line_name} to {dest_name} arrives in: {(eta-now).seconds / 60} minutes')
        arrivals = [{v['line_name']:v['eta']} for v in info['visits'][str(self.stop_id)]]
        return arrivals

class BusLine:
    def __init__(self, operator: str, number: int, direction: int):
        self.operator = operator
        self.number = number
        self.direction = direction
        # cannot get origin/destination since the route json api is not working 
        #self.origin=

    def nextArrivalAtStop(self, stop_id: int):
        stop = BusStop(stop_id)
        all_arrivals = stop.getNextArrivals()
        line_arrival = next(item for item in all_arrivals if str(self.number) in item)

        return line_arrival


def main():
    stop_id = 36560
    stop = BusStop(stop_id)
    line = BusLine('kavim', 69, 1)
    arrival = line.nextArrivalAtStop(stop_id)
    print(arrival)
    #arrivals = stop.getNextArrivals()


class PublicTransportIL(hass.Hass):
    def initialize(self):
        self.

if __name__ == '__main__':
    main()