import random
import json
import io
import xlsxwriter

from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.core.mail import send_mail
from django.db.models import Count
from django.urls import reverse

from .models import Block, BlockLog, Sample, SampleCorrectionRequest


# Fixed email for sending OTP for sample correction
FIXED_OTP_EMAIL = 'example@gmail.com'  # Replace with your actual fixed email


# Ensure fixed blocks exist
def ensure_fixed_blocks():
    fixed_blocks = [
        ("Kolkata (ER)", 125),
        ("Ghaziabad (NR)", 225),
        ("Mumbai (WR)", 50),
        ("Chennai (SR)", 100),
        ("Jaipur (NWR)", 100),
    ]
    for name, cap in fixed_blocks:
        Block.objects.get_or_create(name=name, defaults={'total': cap})


# Allocation with sample code
def allocate_sample_by_code(sample_code):
    if Sample.objects.filter(code=sample_code).exists():
        return [f"Sample code '{sample_code}' already exists."]

    blocks = list(Block.objects.all())
    available_blocks = [b for b in blocks if b.remaining() > 0]

    if not available_blocks:
        return ["No regions have remaining capacity. Allocation failed."]

    weights = [b.remaining() for b in available_blocks]

    selected = random.choices(available_blocks, weights=weights, k=1)[0]

    selected.allocated += 1
    selected.save()

    sample = Sample.objects.create(code=sample_code, block=selected)
    log = BlockLog.objects.create(block=selected, action='allocate', quantity=1)
    log.samples.add(sample)

    return [f"Sample '{sample_code}' allocated to Region {selected.name}."]


# Home view
def home(request):
    ensure_fixed_blocks()

    if request.method == "POST":
        # Allocation form submission
        if "allocate_single" in request.POST:
            sample_code = request.POST.get("sample_code", "").strip()
            if sample_code:
                log = allocate_sample_by_code(sample_code)
                request.session['result'] = {'log': log}
            else:
                request.session['result'] = {'error': "Please enter a valid sample code."}
            # Redirect including anchor to keep scroll position near form after reload
            return redirect(reverse('home') + '#actions')

        # Process specific samples form submission
        elif "process_specific" in request.POST:
            try:
                block_id = int(request.POST.get("processed_block"))
                count = int(request.POST.get("processed_count"))
                block = Block.objects.get(id=block_id)

                if count > block.allocated:
                    request.session['result'] = {
                        'error': f"Region {block.name} only has {block.allocated} allocated samples. Cannot remove {count}."
                    }
                else:
                    block.allocated -= count
                    block.save()
                    BlockLog.objects.create(block=block, action='process', quantity=count)
                    request.session['result'] = {
                        'log': [f"{count} samples processed from region {block.name}. Allocation updated."]
                    }
            except (ValueError, Block.DoesNotExist):
                request.session['result'] = {'error': "Invalid region or sample count."}
            return redirect(reverse('home') + '#actions')

    result = request.session.pop('result', None)
    blocks = Block.objects.all().order_by('name')
    logs = BlockLog.objects.all().order_by('-timestamp')[:20]

    # Prepare chart data: Allocated and Remaining per region
    block_labels = [b.name for b in blocks]
    allocated_list = [b.allocated for b in blocks]
    remaining_list = [b.remaining() for b in blocks]

    return render(request, 'allocationapp/home.html', {
        'result': result,
        'blocks': blocks,
        'logs': logs,
        'block_labels': json.dumps(block_labels),
        'allocated_list': json.dumps(allocated_list),
        'remaining_list': json.dumps(remaining_list),
    })


# Logs view for filter UI
def logs_view(request):
    blocks = Block.objects.all()
    logs = BlockLog.objects.all().order_by('-timestamp')

    block_id = request.GET.get('block')
    action = request.GET.get('action')
    date = request.GET.get('date')

    if block_id:
        logs = logs.filter(block_id=block_id)
    if action:
        logs = logs.filter(action=action)
    if date:
        logs = logs.filter(timestamp__date=date)

    return render(request, 'allocationapp/logs.html', {
        'logs': logs,
        'blocks': blocks,
        'selected_block': block_id,
        'selected_action': action,
        'selected_date': date,
    })


# Excel download with sample code support (enhanced formatting recommended)
def download_logs(request):
    logs = BlockLog.objects.all().order_by('-timestamp')

    block_id = request.GET.get('block')
    action = request.GET.get('action')
    date = request.GET.get('date')

    if block_id and block_id != 'None':
        logs = logs.filter(block_id=block_id)
    if action and action != 'None':
        logs = logs.filter(action=action)
    if date and date != 'None':
        logs = logs.filter(timestamp__date=date)

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet()
    password = "YourSecret123"
    worksheet.protect(password)

    # Define formats
    header_format = workbook.add_format({
        'bold': True,
        'font_color': '#ffffff',
        'bg_color': '#27ae60',  # green header background to match your theme
        'align': 'center',
        'valign': 'vcenter',
        'border': 1,
        'font_size': 12
    })
    cell_format_odd = workbook.add_format({
        'bg_color': "#f9f9f9",
        'border': 1,
        'font_size': 11,
        'valign': 'vcenter'
    })
    cell_format_even = workbook.add_format({
        'bg_color': "#eafaf1",
        'border': 1,
        'font_size': 11,
        'valign': 'vcenter'
    })
    wrap_format = workbook.add_format({
        'bg_color': "#eafaf1",
        'border': 1,
        'font_size': 11,
        'valign': 'vcenter',
        'text_wrap': True
    })

    headers = ['Timestamp', 'Block', 'Action', 'Sample Code or Quantity']
    for col_num, header in enumerate(headers):
        worksheet.write(0, col_num, header, header_format)

    # Set column widths for better readability
    worksheet.set_column('A:A', 20)  # Timestamp
    worksheet.set_column('B:B', 24)  # Block
    worksheet.set_column('C:C', 16)  # Action
    worksheet.set_column('D:D', 32)  # Sample Code or Quantity

    # Freeze header row
    worksheet.freeze_panes(1, 0)

    # Write data rows with alternating row colors
    for row_num, log in enumerate(logs, start=1):
        row_format = cell_format_odd if row_num % 2 == 1 else cell_format_even

        worksheet.write(row_num, 0, log.timestamp.strftime('%Y-%m-%d %H:%M:%S'), row_format)
        worksheet.write(row_num, 1, log.block.name, row_format)
        worksheet.write(row_num, 2, log.get_action_display(), row_format)

        if log.action == 'allocate':
            sample_codes = ", ".join(sample.code for sample in log.samples.all())
            worksheet.write(row_num, 3, sample_codes or '', wrap_format)
        else:
            worksheet.write(row_num, 3, str(log.quantity or ''), row_format)

    workbook.close()
    output.seek(0)

    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="protected_logs.xlsx"'
    return response



# Sample correction: request form to send OTP to fixed email
def request_sample_correction(request):
    if request.method == "POST":
        old_code = request.POST.get('old_sample_code', '').strip()
        new_code = request.POST.get('new_sample_code', '').strip()

        # Validate old code exists; new code doesn't exist
        if not Sample.objects.filter(code=old_code).exists():
            return render(request, 'allocationapp/correction_form.html', {'error': "Old sample code does not exist."})
        if Sample.objects.filter(code=new_code).exists():
            return render(request, 'allocationapp/correction_form.html', {'error': "New sample code already exists."})

        # Create OTP and save request
        otp = f"{random.randint(100000, 999999)}"
        SampleCorrectionRequest.objects.create(
            email=FIXED_OTP_EMAIL,
            old_sample_code=old_code,
            new_sample_code=new_code,
            otp=otp
        )

        # Send OTP to fixed email
        send_mail(
            subject="OTP for Sample Code Correction",
            message=f"Your OTP is {otp}",
            from_email="noreply@yourdomain.com",
            recipient_list=[FIXED_OTP_EMAIL],
            fail_silently=False,
        )

        # Store identifying info in session for OTP verification
        request.session["correction_email"] = FIXED_OTP_EMAIL
        request.session["correction_old_code"] = old_code
        request.session["correction_new_code"] = new_code

        return redirect("verify_correction_otp")

    return render(request, "allocationapp/correction_form.html")


# OTP verification and sample code correction
def verify_correction_otp(request):
    if request.method == "POST":
        email = request.session.get("correction_email")
        old_code = request.session.get("correction_old_code")
        new_code = request.session.get("correction_new_code")
        otp_input = request.POST.get('otp', '').strip()

        try:
            req = SampleCorrectionRequest.objects.filter(
                email=email, old_sample_code=old_code, new_sample_code=new_code, is_verified=False
            ).latest("created_at")
        except SampleCorrectionRequest.DoesNotExist:
            return render(request, "allocationapp/correction_otp.html", {"error": "No pending correction request found."})

        if req.is_expired():
            return render(request, "allocationapp/correction_otp.html", {"error": "OTP has expired."})

        if req.otp != otp_input:
            return render(request, "allocationapp/correction_otp.html", {"error": "Invalid OTP."})

        # OTP valid: mark request verified
        req.is_verified = True
        req.save()

        # Remove old sample and decrement allocated count
        try:
            sample = Sample.objects.get(code=old_code)
            block = sample.block
            if block.allocated > 0:
                block.allocated -= 1
                block.save()
            sample.delete()
        except Sample.DoesNotExist:
            return render(request, "allocationapp/correction_otp.html", {"error": "Old sample not found."})

        # Allocate new sample code
        allocation_log = allocate_sample_by_code(new_code)

        # Clear session data after use (optional cleanup)
        request.session.pop("correction_email", None)
        request.session.pop("correction_old_code", None)
        request.session.pop("correction_new_code", None)

        return render(request, "allocationapp/correction_otp.html", {
            "success": "Sample code corrected successfully.",
            "log": allocation_log,  # optional: log messages after allocation
        })

    return render(request, "allocationapp/correction_otp.html")

