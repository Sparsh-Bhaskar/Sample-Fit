# from django.db import models

# # Create your models here.
# class Block(models.Model):
#     name = models.CharField(max_length=100, unique=True)
#     allocated = models.IntegerField(default=0)
#     total = models.IntegerField(default=100)

#     def remaining(self):
#         return self.total - self.allocated

#     def __str__(self):
#         return f"{self.name}: {self.allocated}/{self.total}"
    
# class BlockLog(models.Model):
#     ACTION_CHOICES = [
#         ('allocate', 'Allocated'),
#         ('process', 'Processed'),
#         ('manual', 'Manually Processed'),
#         ('reset', 'Reset'),
#         ('delete', 'Deleted')
#     ]
    
#     block = models.ForeignKey('Block', on_delete=models.CASCADE)
#     action = models.CharField(max_length=20, choices=ACTION_CHOICES)
#     quantity = models.IntegerField()
#     timestamp = models.DateTimeField(auto_now_add=True)
#     samples = models.ManyToManyField('Sample', blank=True)

#     def __str__(self):
#         return f"{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')} | {self.block.name} | {self.action} | {self.quantity}"

# class Sample(models.Model):
#     code = models.CharField(max_length=100, unique=True)
#     block = models.ForeignKey(Block, on_delete=models.CASCADE)
#     timestamp = models.DateTimeField(auto_now_add=True)

from django.db import models

class Block(models.Model):
    name = models.CharField(max_length=100, unique=True)
    allocated = models.IntegerField(default=0)
    total = models.IntegerField(default=100)

    def remaining(self):
        return self.total - self.allocated

    def __str__(self):
        return f"{self.name}: {self.allocated}/{self.total}"


class Sample(models.Model):
    code = models.CharField(max_length=100, unique=True)
    block = models.ForeignKey(Block, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.code


class BlockLog(models.Model):
    ACTION_CHOICES = [
        ('allocate', 'Allocated'),
        ('process', 'Processed'),
        ('manual', 'Manually Processed'),
        # ('reset', 'Reset'),
        ('delete', 'Deleted'),
    ]

    block = models.ForeignKey(Block, on_delete=models.CASCADE)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    quantity = models.IntegerField(null=True, blank=True)  # Now optional
    timestamp = models.DateTimeField(auto_now_add=True)
    samples = models.ManyToManyField(Sample, blank=True)  # Used for allocation log

    def __str__(self):
        sample_list = ", ".join(s.code for s in self.samples.all())
        return f"{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')} | {self.block.name} | {self.action} | {sample_list or self.quantity}"
