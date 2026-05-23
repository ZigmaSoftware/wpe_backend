"""Project-local DRF router helpers."""

from collections import OrderedDict

from rest_framework.routers import DefaultRouter


class ExtendedDefaultRouter(DefaultRouter):
    """Default router with support for extra named links on the API root."""

    def __init__(self, *args, **kwargs):
        self.extra_api_root_dict = OrderedDict()
        super().__init__(*args, **kwargs)

    def get_api_root_view(self, api_urls=None):
        api_root_dict = OrderedDict()
        list_name = self.routes[0].name

        for prefix, _viewset, basename in self.registry:
            api_root_dict[prefix] = list_name.format(basename=basename)

        api_root_dict.update(self.extra_api_root_dict)
        return self.APIRootView.as_view(api_root_dict=api_root_dict)
