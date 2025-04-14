# Django SuperApp - WhatsApp Integration

A Django app that integrates with the WhatsApp Business API, allowing developers to easily send and receive WhatsApp messages within their Django projects.

## Features

- Send and receive WhatsApp messages through a simple API
- Support for template messages
- Admin interface for message management
- Webhook handling for incoming messages
- Status tracking for sent messages
- Support for media messages

### Getting Started
1. Setup the project using the instructions from https://django-superapp.bringes.io/
2. Setup `sample_app` app using the below instructions:
```bash
cd my_superapp;
cd superapp/apps;
django_superapp bootstrap-app \
    --template-repo https://github.com/django-superapp/django-superapp-sample-app ./sample_app;
cd ../../;
```

### Documentation
For a more detailed documentation, visit [https://django-superapp.bringes.io](https://django-superapp.bringes.io).
