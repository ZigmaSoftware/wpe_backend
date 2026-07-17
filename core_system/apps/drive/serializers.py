from rest_framework import serializers


class DriveUploadSerializer(serializers.Serializer):
    file = serializers.FileField()


class DriveDeleteSerializer(serializers.Serializer):
    id = serializers.CharField()
    permanent = serializers.BooleanField(default=True, required=False)
