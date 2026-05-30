from Truck.models import Customer as CustomerModel
 
 
def create_customer_profile(backend, user, response, *args, **kwargs):
    """
    Ensures every Google OAuth user gets a Customer profile.
    Runs only when a new user is created (is_new=True).
    Couriers will still pass the /customer/ access check.
    """
    if kwargs.get('is_new', False):
        CustomerModel.objects.get_or_create(user=user)
