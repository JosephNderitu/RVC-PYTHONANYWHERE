
## Test the confirmation flow end to end:
docker compose exec web python manage.py shell -c "
from Truck.models import Job
job = Job.objects.get(id='c3023809-2838-47fd-ac08-02d19b5acd82')
print('Confirmation URL:', job.get_confirmation_url())
print('Confirmed:', job.customer_confirmed)
"
## Run to change the job id status
docker compose exec web python manage.py shell -c "from Truck.models import CourierZoneState, GeofenceEvent, Job; CourierZoneState.objects.all().delete(); GeofenceEvent.objects.all().delete(); Job.objects.filter(id='c3023809-2838-47fd-ac08-02d19b5acd82').update(status='picking'); print('Reset done')"

## Running the simulation for geofencing step by step
python gps_replay.py --route atlanta_marietta --speed 2 --pause-at 120 --username Joseph --password Jossey@2003 --job-id c3023809-2838-47fd-ac08-02d19b5acd82

## COMMAND to check weather condition job status creating step3
docker compose exec web python manage.py shell -c "
from Truck.models import Job
j = Job.objects.filter(status='creating').last()
print('Condition:', j.weather_condition)
print('Label:', j.weather_label)
print('Multiplier:', j.weather_eta_multiplier)
print('Duration:', j.duration, 'min')
print('Pickup:', j.pickup_lat, j.pickup_lng)
"
## COMMAND TO CHECK WEATHER
docker compose exec web python3 -c "
import requests

cities = [
    ('Atlanta, GA',      33.749,  -84.388),
    ('Savannah, GA',     32.083,  -81.099),
    ('New Orleans, LA',  29.951,  -90.071),
    ('Seattle, WA',      47.606, -122.332),
    ('Miami, FL',        25.774,  -80.190),
    ('Nashville, TN',    36.174,  -86.767),
    ('Houston, TX',      29.760,  -95.370),
    ('Denver, CO',       39.739, -104.984),
]

WMO = {0:'clear',1:'cloudy',2:'cloudy',3:'cloudy',45:'fog',48:'fog',
       51:'drizzle',53:'drizzle',61:'rain',63:'rain',65:'heavy_rain',
       71:'snow',73:'snow',80:'rain',81:'rain',82:'heavy_rain',
       95:'storm',96:'storm',99:'storm'}
MULT = {'clear':1.0,'cloudy':1.0,'fog':1.15,'drizzle':1.08,
        'rain':1.12,'heavy_rain':1.20,'snow':1.35,'storm':1.25}

for name, lat, lng in cities:
    r = requests.get('https://api.open-meteo.com/v1/forecast',
        params={'latitude':lat,'longitude':lng,'current':'weather_code','timezone':'America/New_York'},timeout=5)
    wmo = r.json()['current']['weather_code']
    cond = WMO.get(int(wmo),'clear')
    mult = MULT.get(cond,1.0)
    flag = '  <-- USE THIS' if mult > 1.0 else ''
    print(f'{name:<22} {cond:<12} x{mult}{flag}')
"