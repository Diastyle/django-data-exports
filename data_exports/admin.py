#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import zipfile
import StringIO

from django.contrib import admin
from data_exports.models import Export, Column, Format
from data_exports.forms import ColumnForm, ColumnFormSet
from django.db import connection
from django.http import HttpResponse

class ColumnInline(admin.TabularInline):
    extra = 0
    form = ColumnForm
    formset = ColumnFormSet
    model = Column





def zipfiles(outfile_dir):
    # Files (local path) to put in the .zip
    # We add all the files in outfile_dir
    filenames = os.listdir(outfile_dir)

    # Folder name in ZIP archive which contains the above files
    # E.g [thearchive.zip]/somefiles/file2.txt
    # FIXME: Set this to something better
    zip_subdir = "exports"
    zip_filename = "%s.zip" % zip_subdir

    # Open StringIO to grab in-memory ZIP contents
    s = StringIO.StringIO()

    # The zip compressor
    zf = zipfile.ZipFile(s, "w")

    for fpath in filenames:
        # Calculate path for file in zip
        fdir, fname = os.path.split(fpath)
        zip_path = os.path.join(zip_subdir, fname)

        # Add file, at correct path
        zf.write(fpath, zip_path)

    # Must close zip for all contents to be written
    zf.close()

    # Grab ZIP file from in-memory, make response with correct MIME-type
    resp = HttpResponse(s.getvalue(), mimetype = "application/x-zip-compressed")
    # ..and correct content-disposition
    resp['Content-Disposition'] = 'attachment; filename=%s' % zip_filename
    return resp

# Adding action to speedup the csv export functionality
def sql_csv_export(modeladmin, request, queryset):
    '''
    Get the models and the export objects.
    Generate the sql to create the csv files
    Create the csv files in a dir in tmp named pert the request session
    Zip the folder
    Serve the folder to the user
    '''
    cursor = connection.cursor()
    outfile_dir = "/tmp/%s/" % (request.META["CSRF_COOKIE"])
    # Make the directory
    if not os.path.exists(outfile_dir):
        os.mkdir(outfile_dir)
    for export in queryset:
       #obj_qs = export.model.model_class().objects.all()
        fields = export.column_set.all().order_by("order").values_list('column', flat=True )
        fields_string = ','.join(fields)
        table_name = export.model.model
        outfile_path = outfile_dir+export.name
        sql_phrase = '''
                     SELECT %s INTO OUTFILE %s FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
                     LINES TERMINATED BY '\n' FROM %s"'
                     ''' % (fields_string, outfile_path, table_name)
        with open(outfile_path, "wb") as export_file:
            export_file.write(fields_string)
        cursor.execute(sql_phrase)
    return zipfiles(outfile_dir)


class ExportAdmin(admin.ModelAdmin):
    inlines = [ColumnInline]
    list_display = ['name', 'slug', 'model', 'export_format',
                    'get_export_link']
    list_filter = ['name', 'export_format', 'model']
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ['model']
    search_fields = ['name', 'slug', 'model']
    actions = ['sql_csv_export']

    def get_readonly_fields(self, request, obj=None):
        """The model can't be changed once the export is created"""
        if obj is None:
            return []
        return super(ExportAdmin, self).get_readonly_fields(request, obj)

    def get_formsets(self, request, obj=None):
        if obj is None:
            return
        if not hasattr(self, 'inline_instances'):
            self.inline_instances = self.get_inline_instances(request)
        for inline in self.inline_instances:
            yield inline.get_formset(request, obj)

    def sql_csv_export(self, request, obj=None):
        return sql_csv_export(self, request, obj)

    def response_add(self, request, obj, post_url_continue='../%s/'):
        """If we're adding, save must be "save and continue editing"

        Two exceptions to that workflow:
        * The user has pressed the 'Save and add another' button
        * We are adding a user in a popup

        """
        if '_addanother' not in request.POST and '_popup' not in request.POST:
            request.POST['_continue'] = 1
        return super(ExportAdmin, self).response_add(request,
                                                     obj,
                                                     post_url_continue)

admin.site.register(Export, ExportAdmin)
admin.site.register(Format)
