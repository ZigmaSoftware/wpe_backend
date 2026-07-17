from rest_framework import serializers


class TaskTrackerCellsSerializer(serializers.Serializer):
    cells = serializers.ListField(
        child=serializers.CharField(allow_blank=True, trim_whitespace=False),
        allow_empty=True,
    )


class TaskTrackerAddRowSerializer(TaskTrackerCellsSerializer):
    pass


class TaskTrackerUpdateRowSerializer(TaskTrackerCellsSerializer):
    row = serializers.IntegerField(min_value=2)


class TaskTrackerDeleteRowSerializer(serializers.Serializer):
    row = serializers.IntegerField(min_value=2)
