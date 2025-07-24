from django.shortcuts import render, redirect
from .models import Block, BlockLog, Sample
import random
from django.http import HttpResponse
import io
import xlsxwriter
from django.db.models import Count
import json

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
            return redirect('home')

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
            return redirect('home')

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


# Excel download with sample code support
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

    headers = ['Timestamp', 'Block', 'Action', 'Sample Code or Quantity']
    for col_num, header in enumerate(headers):
        worksheet.write(0, col_num, header)

    for row_num, log in enumerate(logs, start=1):
        worksheet.write(row_num, 0, log.timestamp.strftime('%Y-%m-%d %H:%M:%S'))
        worksheet.write(row_num, 1, log.block.name)
        worksheet.write(row_num, 2, log.get_action_display())

        if log.action == 'allocate':
            sample_codes = ", ".join(sample.code for sample in log.samples.all())
            worksheet.write(row_num, 3, sample_codes or '')
        else:
            worksheet.write(row_num, 3, str(log.quantity or ''))

    workbook.close()
    output.seek(0)

    response = HttpResponse(output.read(),
                            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="protected_logs.xlsx"'
    return response
