from django.db import models


class EmailAccount(models.Model):
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=100)


class File(models.Model):
    file = models.FileField(upload_to='uploads/')
    name = models.CharField(max_length=255, default='unknown')


class Messages(models.Model):
    subject = models.CharField(max_length=255, blank=True)
    date_of_dispatch = models.DateTimeField(blank=True)
    date_of_receipt = models.DateTimeField(blank=True)
    text = models.TextField(blank=True)
    email_account = models.ForeignKey(EmailAccount, on_delete=models.CASCADE)
    files = models.ManyToManyField(File, blank=True)