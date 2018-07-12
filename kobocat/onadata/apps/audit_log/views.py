from django.http import (
    HttpResponseRedirect, HttpResponse)
from django.shortcuts import render_to_response,render,get_object_or_404
from django.template import RequestContext,loader
#from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST
import json
import sys

from onadata.apps.logger.models import Instance, XForm
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.db import connection

from onadata.libs.utils.user_auth import has_permission, get_xform_and_perms,\
    helper_auth_helper, has_edit_permission
from onadata.libs.utils.log import audit_log, Actions

# Create your views here.

@login_required
def audit_log_main(request):
    username = request.user
    _DATETIME_FORMAT_SUBMIT = '%Y-%m-%d'
    audit_log_view_json = {}
	
    xform_id = 0
    instance_id = 0
    cursor = connection.cursor()
    get_all_query = "SELECT id,form_id,instance_id,old_json,new_json,change_time FROM audit_logger_instance order by change_time desc"
    cursor.execute(get_all_query)
    xform_instances = cursor.fetchall()
    rowcount = cursor.rowcount
    # print('xform::',xform_instances)
    for xform in xform_instances:


        data_id = xform[0]
        xform_id = xform[1]
        instance_id = xform[2]
        row_data = {}
        try:
            xform_obj = XForm.objects.get(pk=xform_id)
            json_data = json.dumps(xform[3])
            submittedBy = get_username(str(json_data))
            row_data['form_title'] = xform_obj.title
            row_data['form_id_string'] = xform_obj.id_string
            row_data['instance_id'] = instance_id
            row_data['submittedBy'] = submittedBy
            row_data['form_time'] = xform[5].strftime(_DATETIME_FORMAT_SUBMIT)
            row_data['data_id'] = data_id
            key = "instances"

            xform, is_owner, can_edit, can_view = get_xform_and_perms(
        username, xform_obj.id_string, request)
            # print('is_owner, can_edit, can_view', is_owner,can_edit,can_view)
            if (xform.shared_data or can_view or request.session.get('public_link') == xform.uuid):
                audit_log_view_json.setdefault(key, [])
                audit_log_view_json[key].append(row_data)
        except Exception, e: #XForm.DoesNotExist
            print('corresponding xfomr not present',e)
            xform_obj = None
            #xform_obj = XForm.objects.get(pk=xform_id)



    print 'audit_log_view_json::----'
    print audit_log_view_json
    response = HttpResponse()
    variables = RequestContext(request, {
    	'head_title': 'Project Summary',
    	'log_detail':json.dumps(audit_log_view_json),
    	'request_user': username,
    	})
    response = render(request,'audit_log/audit_main_view.html'
    	,variables)

    return response


def get_username(json_data):

	data = json.loads(json_data)
	print 'data json'
	return data['_submitted_by']

@login_required
def instance_diff(request, username, id_string,instance_id,data_id):
    xform, is_owner, can_edit, can_view = get_xform_and_perms(
        username, id_string, request)
    # no access
    if not (xform.shared_data or can_view or
            request.session.get('public_link') == xform.uuid):
        return HttpResponseForbidden(_(u'Not shared.'))

    return render(request, 'audit_log/submission_diff.html', {
        'username': username,
        'id_string': id_string,
        'xform': xform,
        'can_edit': can_edit,
        'instance_id': instance_id,
        'data_id':data_id,
    })

@login_required
def getInstance_json(request, username, id_string, instance_id, data_id):
    print 'Entered------------------------------------------------------'
    print data_id
    xform = get_object_or_404(
        XForm, user__username__iexact=username, id_string__exact=id_string)

    cursor = connection.cursor()
    old_json_query = "SELECT old_json FROM audit_logger_instance WHERE form_id = "+str(xform.id)+" AND instance_id = "+instance_id+" AND id = "+data_id+""
    cursor.execute(old_json_query)
    xform_instance = cursor.fetchone();
    rowcount = cursor.rowcount
    #print 'data ::-----------------'
    # print xform_instance
    response = HttpResponse()
    response.content = json.dumps(xform_instance[0])
    return response

@login_required
def getInstance_new_json(request, username, id_string, instance_id, data_id):
    print 'Entered New Json-----------------------------'
    print data_id
    xform = get_object_or_404(
        XForm, user__username__iexact=username, id_string__exact=id_string)
    
    cursor = connection.cursor()
    new_json_query = "SELECT new_json FROM audit_logger_instance WHERE form_id="+str(xform.id)+" AND instance_id = "+instance_id+" AND id = "+data_id+""
    cursor.execute(new_json_query)
    xform_instance = cursor.fetchone();
    rowcount = cursor.rowcount
    #print 'data ::-----------------'
    # print xform_instance
    response = HttpResponse()
    response.content = json.dumps(xform_instance[0])
    return response