
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