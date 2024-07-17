from django.utils import timezone
import uuid
from django.db import models
from django.contrib.auth.models import User

class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    avatar = models.ImageField(upload_to='customer/avatars/', blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=255,blank=True)
    stripe_payment_method_id = models.CharField(max_length=255,blank=True)
    stripe_card_last4 = models.CharField(max_length=255,blank=True)
    phone_number = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.user.get_full_name()
    
    
class Courier(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    lat = models.FloatField(default=0)
    lng = models.FloatField(default=0)
    paypal_email = models.EmailField(max_length=255, blank=True)
    fcm_token = models.TextField(blank=True)
    
    
    def __str__(self):
        return self.user.get_full_name()
    
    
class Category(models.Model):   
    slug = models.CharField(max_length=255,  unique=True)
    name = models.CharField(max_length=255)
    
    def __str__(self):
        return self.name
    
class Job(models.Model):
    SMALL_SIZE ="small"
    MEDIUM_SIZE ="medium"
    LARGE_SIZE ="large"
    SIZES  = (
            (SMALL_SIZE, "Small"),
            (MEDIUM_SIZE,"Medium"),
            (LARGE_SIZE, "Large")
          )
    CREATING_STATUS = 'creating'
    PROCESSING_STATUS = 'processing'
    PICKING_STATUS = 'picking'
    DELIVERING_STATUS = 'delivering'
    COMPLETED_STATUS = 'completed'
    CANCELED_STATUS = 'cancel'
    STATUSES = (
             (CREATING_STATUS, "Creating..."),
             (PROCESSING_STATUS, "Processing.."),
             (PICKING_STATUS, "Picking up the item."),
             (DELIVERING_STATUS, "Delivering to customer."),
             (COMPLETED_STATUS, "Completed!"),
             (CANCELED_STATUS, "Cancelled.")
           )
    
    #Step_1
    id = models.UUIDField(primary_key=True,default=uuid.uuid4, editable=False)
    Customer = models.ForeignKey(Customer,on_delete=models.CASCADE)
    courier = models.ForeignKey(Courier,on_delete=models.CASCADE, null=True, blank=True)
    names = models.CharField(max_length=255)
    description = models.CharField(max_length=255)
    category =models.ForeignKey(Category,on_delete=models.SET_NULL,null=True,blank=True)
    size = models.CharField(max_length=20 ,choices=SIZES, default=MEDIUM_SIZE)
    quantity = models.IntegerField(default=1)
    photo = models.ImageField(upload_to='job/photo/')
    status = models.CharField(max_length=20 , choices=STATUSES, default=CREATING_STATUS)
    created_at = models.DateTimeField(default=timezone.now)
    
    #step2
    pickup_address = models.CharField(max_length=255, blank=True)
    pickup_lat = models.FloatField(default=0.0)
    pickup_lng = models.FloatField(default=0.0)
    pickup_name = models.CharField(max_length=255, blank=True)
    pickup_phone = models.CharField(max_length=255, blank=True)
    
    #step3
    delivery_address = models.CharField(max_length=255, blank=True)
    delivery_lat = models.FloatField(default=0.0)
    delivery_lng = models.FloatField(default=0.0)
    delivery_name = models.CharField(max_length=255, blank=True)
    delivery_phone = models.CharField(max_length=255, blank=True)
    
    #step4
    duration = models.IntegerField(default=0)
    distance = models.FloatField(default=0)
    price = models.FloatField(default = 0)
    
    #Extra Information
    pickup_photo = models.ImageField(upload_to='job/pickup_photos/', null=True, blank=True)
    pickedup_at = models.DateTimeField(null=True, blank=True)
    
    
    delivery_photo = models.ImageField(upload_to='job/delivery_photos/', null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
     return f"{self.names} - {self.Customer}"

     
     #TRansactions


class Transaction(models.Model):
    IN_STATUS = "in"
    OUT_STATUS = "out"
    STATUSES = (
        (IN_STATUS, 'in'),
        (OUT_STATUS, 'out'),
    )
    
    stripe_payment_intent_id = models.CharField(max_length=255, unique=True)
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    amount =  models.FloatField(default=0)
    status = models.CharField(max_length=20, choices=STATUSES, default=IN_STATUS)
    created_at = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return self.stripe_payment_intent_id
    
    
    
    
    #my additions knowledge

class Truck(models.Model):
    image = models.ImageField(upload_to='truck_images/')
    name = models.CharField(max_length=100)
    description = models.TextField()
    
    def __str__(self):
        return self.name

class Service(models.Model):
    image = models.ImageField(upload_to='service_images/')
    title = models.CharField(max_length=100)
    description = models.TextField()
    
    def __str__(self):
        return self.title

class Worker(models.Model):
    image = models.ImageField(upload_to='worker_images/')
    name = models.CharField(max_length=100)
    job_title = models.CharField(max_length=100)
    description = models.TextField()
    
    def __str__(self):
        return self.name

class Owner(models.Model):
    image = models.ImageField(upload_to='owner_images/')
    name = models.CharField(max_length=100)
    job_title = models.CharField(max_length=100)
    description = models.TextField()
    
    def __str__(self):
        return self.name
