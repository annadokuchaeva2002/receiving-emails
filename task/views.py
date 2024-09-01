from django.http import HttpResponse, Http404
from django.shortcuts import render, redirect
from .forms import EmailLoginForm
import imaplib
import email
from email.header import decode_header
from django.utils import timezone
from .models import Messages, EmailAccount, File
from django.core.files.base import ContentFile


def fetch_emails(email_address, password):
    imap_settings = {
        'gmail.com': ('imap.gmail.com', 993),
        'mail.ru': ('imap.mail.ru', 993),
        'yandex.ru': ('imap.yandex.ru', 993),
    }

    domain = email_address.split('@')[1]
    if domain not in imap_settings:
        raise ValueError("Unsupported email provider")

    imap_server, port = imap_settings[domain]

    try:
        mail = imaplib.IMAP4_SSL(imap_server, port)
        mail.login(email_address, password)
        mail.select('inbox')

        status, messages = mail.search(None, 'ALL')
        if status != 'OK':
            print("Ошибка при поиске писем.")
            return
        email_ids = messages[0].split()
        total_messages = len(email_ids)

        for index, email_id in enumerate(email_ids):
            res, msg = mail.fetch(email_id, '(RFC822)')
            if res != 'OK':
                print(f"Ошибка при получении письма с ID {email_id}.")
                continue

            msg = email.message_from_bytes(msg[0][1])
            subject, encoding = decode_header(msg['Subject'])[0]
            if isinstance(subject, bytes):
                subject = subject.decode(encoding if encoding else 'utf-8')

            date_of_dispatch = email.utils.parsedate_to_datetime(msg['Date'])
            date_of_receipt = timezone.now()

            text = ""
            files = []
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        text = part.get_payload(decode=True).decode()
                    elif part.get_content_disposition() == 'attachment':
                        file_name = part.get_filename()
                        if file_name:
                            file_data = part.get_payload(decode=True)
                            file_instance = File()
                            file_instance.file.save(file_name, ContentFile(file_data))
                            file_instance.name = file_name
                            file_instance.save()
                            files.append(file_instance)
            else:
                text = msg.get_payload(decode=True).decode()

            message_instance = Messages.objects.create(
                subject=subject,
                date_of_dispatch=date_of_dispatch,
                date_of_receipt=date_of_receipt,
                text=text,
                email_account=EmailAccount.objects.get(email=email_address),
            )
            message_instance.files.set(files)

            percentage = (index + 1) / total_messages * 100
            print(f"Получено сообщений: {index + 1}/{total_messages} ({percentage:.2f}%)")

    except imaplib.IMAP4.error as e:
        print(f"IMAP ошибка: {e}")
    finally:
        mail.logout()


def login_view(request):
    if request.method == 'POST':
        form = EmailLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']

            existing_account = EmailAccount.objects.filter(email=email).first()
            if existing_account:
                existing_account.delete()

            EmailAccount.objects.create(email=email, password=password)
            fetch_emails(email, password)
            return redirect('messages')
    else:
        form = EmailLoginForm()

    return render(request, 'login.html', {'form': form})


def messages_view(request):
    messages = Messages.objects.prefetch_related('files').all()
    return render(request, 'messages.html', {'messages': messages})


def download_file(request, file_id):
    try:
        file_instance = File.objects.get(id=file_id)
        response = HttpResponse(file_instance.file, content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{file_instance.name}"'
        return response
    except File.DoesNotExist:
        raise Http404("Файл не найден")
