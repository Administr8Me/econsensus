# Create your views here.
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.views.generic import list_detail
from django.http import HttpResponse
from django.utils.translation import ugettext_lazy as _

import unicodecsv

from models import Decision, Feedback
from forms import DecisionForm, FeedbackFormSet
from forms import SortForm

#TODO: Exporting as csv is a generic function that can be required of any database.
#Therefore it should be its own app.
#This looks like it's already been done... see https://github.com/joshourisman/django-tablib
def export_csv(request):
    ''' Create the HttpResponse object with the appropriate CSV header and corresponding CSV data from Decision.
        Expected input: request (not quite sure what this is!)
        Expected output: http containing MIME info followed by the data itself as CSV.
        >>> res = export_csv(1000)
        >>> res.status_code
        200
        >>> res['Content-Disposition']
        'attachment; filename=publicweb_decision.csv'
        >>> res['Content-Type']
        'text/csv'
        >>> len(res.content)>0
        True
        '''

    def fieldOutput(obj, field):
        '''Looks up the status_text() for status, otherwise just returns the getattr for the field'''
        if field == 'status':
            return obj.status_text()
        else:
            return getattr(obj, field)

    opts = Decision._meta #@UndefinedVariable
    field_names = set([field.name for field in opts.fields])

    response = HttpResponse(mimetype='text/csv')
    response['Content-Disposition'] = 'attachment; filename=%s.csv' % unicode(opts).replace('.', '_')

    writer = unicodecsv.writer(response)
    # example of using writer.writerow: writer.writerow(['First row', 'Foo', 'Bar', 'Baz'])
    writer.writerow(list(field_names))
    for obj in Decision.objects.all():
        writer.writerow([unicode(fieldOutput(obj, field)).encode("utf-8","replace") for field in field_names])
    return response

# TODO: a better way to handle all these list views is to create a single view for listing items
# that view will use a search function that takes a 'filter' parameter and an 'order_by' parameter and gives an ordered queryset back.
# The list view will use a single template but will pass a parameter as extra context to individualise the page

proposal_context = {'page_title' : _("Current Active Proposals"), # pylint: disable=E1102
                     'class' : 'proposal',
                     'columns': ('id', 'excerpt', 'feedbackcount', 'deadline')}

decision_context = {'page_title' : _("Decisions Made"), # pylint: disable=E1102
                     'class' : 'decision',
                     'columns': ('id', 'excerpt', 'decided_date', 'review_date')}

archived_context = {'page_title' : _("Archived Decisions"), # pylint: disable=E1102
                     'class' : 'archived',
                     'columns': ('id', 'excerpt', 'created_date', 'archived_date')}

context_list = { 'proposal' : proposal_context,
             'decision' : decision_context,
             'archived' : archived_context,
             }

#Codes are used to dodge translation in urls.
#Need to think of a better way to do this...
context_codes = { 'proposal' : Decision.PROPOSAL_STATUS,
             'decision' : Decision.DECISION_STATUS,
             'archived' : Decision.ARCHIVED_STATUS,
             }

@login_required        
def listing(request, status):
    extra_context = context_list[status]
    extra_context['sort_form'] = SortForm(request.GET)
    status_code = context_codes[status]
    
    queryset = _filter(_sort(request), status_code)
    
    return list_detail.object_list(
        request,
        queryset,
        template_name = 'consensus_list.html',
        extra_context = extra_context
        )

@login_required
def modify_decision(request, decision_id = None, status_id = None):
    if decision_id is None:
        decision = Decision()
        if status_id is not None:
            decision.status = int(status_id)
    else:
        decision = get_object_or_404(Decision, id = decision_id)
    
    if request.method == "POST":
        if request.POST.get('submit', None) == "Cancel":
            return_page = unicode(decision.status_text())            
            return HttpResponseRedirect(reverse(listing, args=[return_page]))
        
        else:
            decision_form = DecisionForm(data=request.POST, 
                                         instance=decision)
            feedback_formset = FeedbackFormSet(data=request.POST, 
                                               instance=decision)

            if decision_form.is_valid():
                decision = decision_form.save(commit=False)
                feedback_formset = FeedbackFormSet(request.POST, 
                                                   instance=decision)
                if feedback_formset.is_valid():
                    decision.save(request.user)
                    if decision_form.cleaned_data['watch']:
                        decision.add_watcher(request.user)
                    else:
                        decision.remove_watcher(request.user)
                    feedback_formset.save()

                    return_page = unicode(decision.status_text())
                    return HttpResponseRedirect(reverse(listing, args=[return_page]))

    else:
        feedback_formset = FeedbackFormSet(instance=decision)
        decision_form = DecisionForm(instance=decision)

    return render_to_response('decision_edit.html',
        RequestContext(request,
            dict(decision_form=decision_form, feedback_formset=feedback_formset)))

@login_required
def add_decision(request):
    return modify_decision(request)

@login_required
def add_decision_status(request, status_id):
    return modify_decision(request, status_id = status_id)

@login_required    
def edit_decision(request, decision_id):
    return modify_decision(request, decision_id = decision_id)

@login_required
def inline_edit_decision(request, decision_id, template_name="decision_detail.html"):
    if decision_id is None:
        decision = None
    else:
        decision = get_object_or_404(Decision, id = decision_id)

    if request.method == "POST":
        if request.POST.get('submit', None) == "Cancel":
            return HttpResponseRedirect(reverse("view_decision", args=[decision_id]))

        else:
            decision_form = DecisionForm(data=request.POST, 
                                         instance=decision)
            if decision_form.is_valid():
                decision = decision_form.save(commit=False)
                decision.save(request.user)
                return HttpResponseRedirect(reverse("view_decision", args=[decision_id]))
    else:
        decision_form = DecisionForm(instance=decision)

    return render_to_response(template_name,
        RequestContext(request,
            dict(object=decision, decision_form=decision_form, show_form=True)))

def calculate_svg_bars(feedback_counts, max_height):
    '''
    Calculate ratios for SVG chart because Django's templating is too limited.
    Zero count feedback should still have a small bar because it makes
    chart prettier (currently set to 2 pixel height).

    Custom template tag might be more appropriate with less obvious usage.
    '''
    min_height = 2
    heights = dict(max_height=max_height)

    max_value = max([ feedback_counts[key] for key in feedback_counts if key != 'all' ])
    if max_value == 0: # Special case: no feedback
        max_value = 1
    height_ratio = max_height / max_value

    for feedback_type in feedback_counts:
        bar_height = int(max(round(feedback_counts[feedback_type] * height_ratio), min_height))
        heights[feedback_type] = {
            'height': bar_height,
            'left': max_height - bar_height # Empty column space needed for SVG drawing
        }
    return heights

@login_required
def view_decision(request, decision_id, template_name="decision_detail.html"):
    decision = get_object_or_404(Decision, id = decision_id)
    feedback_stats = {'all': 0,
                      'question': 0,
                      'danger': 0,
                      'concern': 0,
                      'consensus': 0
                     }
    feedback_list = []

    # Bookkeeping
    for feedback in decision.feedback_set.all():
        item = {
            'description': feedback.description
        }
        if feedback.rating == Feedback.QUESTION_STATUS:
            feedback_stats['question'] += 1
            item['type'] = 'question'
        elif feedback.rating == Feedback.DANGER_STATUS:
            feedback_stats['danger'] += 1
            item['type'] = 'danger'
        elif feedback.rating == Feedback.SIGNIFICANT_CONCERNS_STATUS:
            feedback_stats['concern'] += 1
            item['type'] = 'concern'
        else:
            feedback_stats['consensus'] += 1
            item['type'] = 'consensus'
        feedback_stats['all'] += 1
        feedback_list.append(item)

    bars = calculate_svg_bars(feedback_stats, 36)

    return render_to_response(template_name,
        RequestContext(request,
            dict(object=decision, feedback_stats=feedback_stats, bars=bars, feedback_list=feedback_list)))

def _sort(request):
    sort_form = SortForm(request.GET)
    if sort_form.is_valid() and sort_form.cleaned_data['sort']:
        order = str(sort_form.cleaned_data['sort'])
    else:
        order = '-id'

    return Decision.objects.order_by(order)

def _filter(queryset, status):    
    return queryset.filter(status=status)

