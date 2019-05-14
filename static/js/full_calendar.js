// Class to hold an entry instance
// Used to JSONify a string to pass along to Django (much cleaner)
function Entry()
{
	this.id = '';
	this.project = '';
	this.date = '';
	this.hours = '';
	this.comments = '';
	this.issue = '';
	this.activity = '';
}

var EntryList = new Array();

// Main function that is called once the page is loaded.
// This function selects the previous month for the user automatically.
// It also sets an "onchange" event for each checkbox - this is used to keep track, using local storage, the selected items.
function init()
{

    // make a call to get all of our info we need to fill out our time entries and options
	$.ajax({
		url: '../get_dates',
		dataType: "json",
		success: function(data){
			// setup the month list
			var months = data.months;
			for(var i = 0; i < months.length; i++)
			{
				// create a new OPTION
				var option = document.createElement("li");
                var option_link = document.createElement("a");

				option_link.value = months[i].number;
				option_link.innerHTML = months[i].name;
                option_link.name = 'month';
                $(option_link).css('cursor', 'pointer');
                $(option_link).click(function(){
                    $('#month_name').html(this.innerHTML);
                    $('#month_name').val(this.value);
                    GetEntries();
                });
                $(option).append(option_link);

				// add this option to our month select
				$('#month_dropdown').append(option);
			}		

			// setup the year list	
			var years = data.years;
			for(var i = 0; i < years.length; i++)
			{
				// create a new OPTION
				var option = document.createElement("li");
                var option_link = document.createElement("a");

				option_link.value = years[i].year;
				option_link.innerHTML = years[i].year;
                $(option_link).css('cursor', 'pointer');
                $(option_link).click(function(){
                    $('#year_name').html(this.innerHTML);
                    $('#year_name').val(this.value);
                    GetEntries();
                });
                $(option).append(option_link);

				// add this option to our month select
				$('#year_dropdown').append(option);
			}

			// add one more year (so we can look at next year if desired)
            // create a new OPTION
            var option = document.createElement("li");
            var option_link = document.createElement("a");

            option_link.value = years[years.length-1].year + 1;
            option_link.innerHTML = years[years.length-1].year + 1;
            $(option_link).css('cursor', 'pointer');
            $(option_link).click(function(){
                $('#year_name').html(this.innerHTML);
                $('#year_name').val(this.value);
                GetEntries();
            });
            $(option).append(option_link);

            // add this option to our month select
            $('#year_dropdown').append(option);

			Establish();
		},
		error: function(){
			alert("Could not get time entries.  Please contact the system administrator.");
		}
	});

}

function Establish()
{

	// check if we want to look up a specific user...
	if(window.location.href.indexOf('=') > 0)
	{
		TARGET = window.location.href.split('=')[1];
	}

	//------------- Setting up Current Month ------------------//
	var now = new Date();
	var this_year = now.getFullYear();
	var this_month = now.getMonth() + 1;

	// now select this month from the drop-down list
    // find the month for this month
    $('a[name="month"]').each(function(){
       if($(this).val() == this_month)
       {
           $('#month_name').html($(this).html());
           $('#month_name').val(this.value);
       }
    });

	//$('#month_name').html(this_month);

	// and now select this year
	$('#year_name').html(this_year);
    $('#year_name').val(this_year);

	//--------------- Setup Click Events for Certain Column Headers ----------------------------------//
	$('.project_header').click(function(){
		if(ORDER_BY == 'project')
			SwapOrder();
		else
			ORDER = 'asc';
		ORDER_BY = 'project';
		GetEntries();
	});

	$('.date_header').click(function(){
		if(ORDER_BY == 'date')
			SwapOrder();
		else
			ORDER = 'asc';
		ORDER_BY = 'date';
		GetEntries();
	});

	$('.hours_header').click(function(){
		if(ORDER_BY == 'hours')
			SwapOrder();
		else
			ORDER = 'asc';
		ORDER_BY = 'hours';
		GetEntries();
	});

	$('.activity_header').click(function(){
		if(ORDER_BY == 'activity')
			SwapOrder();
		else
			ORDER = 'asc';
		ORDER_BY = 'activity';
		GetEntries();
	});




	GetEntries();
}

function SwapOrder()
{
	if(ORDER == 'asc')
		ORDER = 'desc';
	else
		ORDER = 'asc';
}

// Who is logged in...?
var USER = '';

// MANAGERES ONLY
// do we have a targeted user?
var TARGET = '';

// how are we ordering the views?
var ORDER_BY = 'project';
var ORDER = 'asc';

// list of holidays
var HOLIDAYS = new Array();

// list of activities
var ACTIVITIES = new Array();

var EXPECTED_BILLABLE = '';

function GetEntries()
{
    // make sure to clear out any open dialogs
    $('.ui-dialog').each(function(){
        $(this).remove();
    });

    $('#status_update').html("Getting time entries...");
    $('#calendar').fullCalendar('destroy');
    DAY_HOURS = new Array();

	// make sure we clear our DIV
	$('#entry_list').html('');

	// which target should we use?
	var target_user = $('#username').val();
	if(TARGET != '')
	{
		target_user = TARGET;
	}

	// now that we have our date setup, let's get our entries!
	$.ajax({
		url: '../get_entries',
		data: {month: $('#month_name').val(), year: $('#year_name').val(), target: target_user, order: ORDER_BY, by: ORDER},
		dataType: 'json',
		success: function(data){
			// first check if we passed the "tests"
			if(data == "I'm afraid I can't do that...")
			{
				document.write('<img src="/reports/media/img/no.png" />');
				document.close();
				return;
			}
			// did we get any back?
			/*if(data.result == 'No Entries')
			{
				$('#entry_list').html('<div style="width: 100%; padding-top: 20px; text-align: center;">No Entries</div>');
				return;
			}*/
            // create a default date
            var default_date = new Date();
            default_date.setMonth($('#month_name').val() - 1);
            default_date.setFullYear($('#year_name').val());

            EXPECTED_BILLABLE = data.billable;

            // setup the total hours
			var total_hours = data.total;
			$('#billable_hours').html(total_hours);

			// setup the non-billable hours
			var support = data.support;
			$('#support_hours').html(support);

			// setup total
			$('#total_hours').html(parseFloat(support) + parseFloat(total_hours));

            // create a new calendar
            $('#calendar').fullCalendar({
                defaultDate: default_date,
                 eventClick: function(event, jsEvent, view) {
                    // make sure to clear out any open dialogs
    $('.ui-dialog').each(function(){
        $(this).remove();
    });
                     // fill in our activities
                     $.ajax({
                            url: '../get_activities',
                            data: {'project': event.project_id},
                            dataType: 'json',
                            success: function(data){
                                ACTIVITIES = new Array();
                                for(var i = 0; i < data.length; i++)
                                {
                                    var new_activity = {
                                        id: data[i].id,
                                        name: data[i].name
                                    };
                                    ACTIVITIES.push(new_activity);
                                }
                            },
                            error: function(){
                                console.log("Failed to get activity list")
                            }
                        });
                     var dialog = document.createElement("div");
                     $(dialog).attr('title', event.title);
                     dialog.id = 'dialog_'+event.id;

                     $(dialog).append('<div style="font-size: 10px; text-align: center;">'+event.date+'</div>');
                     // create a small table
                     var table = document.createElement("table");
                     table.className = 'table';
                     $(table).css('width', '100%');
                     $(table).css('table-layout', 'fixed');
                     $(table).css('font-size', '12px');

                     // --- HOURS --- //
                     var hour_row = document.createElement("tr");
                     var hour_title = document.createElement('td');
                     $(hour_title).html('Hours');
                     var hour_val = document.createElement('td');
                     $(hour_val).html(event.hours);
                     $(hour_val).css('text-align', 'right');
                     $(hour_val).attr('edit_mode', 'false');
                     hour_val.id = 'hour_val_'+event.id;
                     $(hour_val).click(function(){
                         // are we in edit mode already?
                         if($(this).attr('edit_mode') == 'true')
                            return;
                         $(this).attr('edit_mode', 'true');
                         // create a new text input
                         var hour_input = document.createElement("input");
                         hour_input.id = 'hour_input_'+this.id.split('_')[2];
                         $(hour_input).css('width', '50px');
                         $(hour_input).val($(this).html());
                         $(hour_input).change(function(){
                                var id = this.id.split('_')[2];
                             $('#calendar').fullCalendar('clientEvents', [id])[0].changes = true;
                         });
                         $(this).html(hour_input);
                         $(hour_input).focus();
                     });
                     $(hour_val).focusout(function(){
                         // are we in edit mode?
                         if($(this).attr('edit_mode') == 'false')
                            return;
                         // grab the value from the text box
                         var val = $('#hour_input_'+this.id.split('_')[2]).val();
                         // update the value
                         $(this).html(val);
                         $(this).attr('edit_mode', 'false');
                     });
                     $(hour_row).append(hour_title);
                     $(hour_row).append(hour_val);
                     $(table).append(hour_row);

                     // --- Comments --- //
                     var comments_row = document.createElement("tr");
                     var comments_title = document.createElement('td');
                     $(comments_title).html('Comments');
                     var comments_val = document.createElement('td');
                     $(comments_val).html(event.comments);
                     comments_val.id = 'comments_val_'+event.id;
                     $(comments_val).css('text-align', 'right');
                     $(comments_val).attr('edit_mode', 'false');
                     $(comments_val).click(function(){
                         // are we in edit mode already?
                         if($(this).attr('edit_mode') == 'true')
                            return;
                         $(this).attr('edit_mode', 'true');
                         // create a new text input
                         var comments_input = document.createElement("input");
                         comments_input.id = 'comments_input_'+this.id.split('_')[2];
                         $(comments_input).css('width', '100px');
                         $(comments_input).val($(this).html());
                         $(comments_input).change(function(){
                             var id = this.id.split('_')[2];
                             $('#calendar').fullCalendar('clientEvents', [id])[0].changes = true;
                         });
                         $(this).html(comments_input);
                         $(comments_input).focus();
                     });
                     $(comments_val).focusout(function(){
                         // are we in edit mode?
                         if($(this).attr('edit_mode') == 'false')
                            return;
                         // grab the value from the text box
                         var val = $('#comments_input_'+this.id.split('_')[2]).val();
                         // update the value
                         $(this).html(val);
                         $(this).attr('edit_mode', 'false');
                     });

                     $(comments_row).append(comments_title);
                     $(comments_row).append(comments_val);
                     $(table).append(comments_row);

                     // --- Activity --- //
                     var activity_row = document.createElement("tr");
                     var activity_title = document.createElement('td');
                     $(activity_title).html('Activity');
                     var activity_val = document.createElement('td');
                     $(activity_val).html(event.activity);
                     $(activity_val).val(event.activity_id);
                     activity_val.id = 'activity_val_'+event.id;
                     $(activity_val).css('text-align', 'right');
                     $(activity_val).attr('edit_mode', 'false');
                     $(activity_val).click(function(){
                         // are we in edit mode already?
                         if($(this).attr('edit_mode') == 'true')
                            return;
                         $(this).attr('edit_mode', 'true');
                         var activity_input = document.createElement("SELECT");
                         activity_input.id = 'activity_input_'+this.id.split('_')[2];
                         $(activity_input).css('width', '100px');
                         for(var i = 0; i < ACTIVITIES.length; i++)
                         {
                             var new_option = document.createElement("option");
                             new_option.value = ACTIVITIES[i].id;
                             $(new_option).html(ACTIVITIES[i].name);
                             if(ACTIVITIES[i].name == $(this).html())
                                $(new_option).attr('selected', 'selected');
                             $(activity_input).append(new_option);
                         }
                         $(activity_input).change(function(){
                             var id = this.id.split('_')[2];
                             $('#calendar').fullCalendar('clientEvents', [id])[0].changes = true;
                         });
                         $(this).html(activity_input);
                         $(activity_input).focus();
                     });
                     $(activity_val).focusout(function(){
                         // are we in edit mode?
                         if($(this).attr('edit_mode') == 'false')
                            return;
                         // grab the value from the text box
                         var val = $('#activity_input_'+this.id.split('_')[2]+' option:selected').text();
                         var value = $('#activity_input_'+this.id.split('_')[2]+' option:selected').val();
                         // update the value
                         $(this).html(val);
                         $(this).val(value);
                         $(this).attr('edit_mode', 'false');
                     });


                     $(activity_row).append(activity_title);
                     $(activity_row).append(activity_val);
                     $(table).append(activity_row);
                     $(dialog).append(table);

                     // --- Action Buttons --- //
                     var button_row = document.createElement("div");
                     $(button_row).css("text-align", 'right');


                     // -- Save Button
                     var save_button = document.createElement("button");
                     $(save_button).addClass("btn");
                     $(save_button).addClass("btn-success");
                     $(save_button).css('float', 'left');
                     //$(save_button).css('margin-left', '20px');
                     $(save_button).html('<i class="fa fa-save"></i>');
                     $(save_button).attr('title', 'Save Changes');
                     //$(save_button).attr('disabled', 'disabled');
                     save_button.id = 'save_'+event.id;
                     $(save_button).click(function(){
                         var id = this.id.split("_")[1];
                         $('#calendar').fullCalendar('clientEvents', [id])[0].hours = $('#hour_val_'+id).html();
                         $('#calendar').fullCalendar('clientEvents', [id])[0].comments = $('#comments_val_'+id).html();
                         $('#calendar').fullCalendar('clientEvents', [id])[0].activity_id = $('#activity_val_'+id).val();
                         $('#calendar').fullCalendar('clientEvents', [id])[0].activity = $('#activity_val_'+id).html();
                         // get the event object
                         var event = $('#calendar').fullCalendar('clientEvents', [id])[0];

                         $.ajax({
                            url: '../update_entry_data',
                            data: {id: id, project: event.project, comments: event.comments, date: event.start.format(), hours: event.hours, target: $('#username').val(), activity: event.activity_id},
                            dataType: 'text',
                            success: function(){
                                console.log("Update successful");
                                $('#calendar').fullCalendar('clientEvents', [id])[0].changes = false;
                                $('#dialog_'+id).remove();
                            },
                            error: function(){
                                alert("Failed to update entry.");
                            }

                        });
                     });
                     $(button_row).append(save_button);

                     // -- Copy Button
                     var copy_button = document.createElement("button");
                     $(copy_button).addClass("btn");
                     $(copy_button).addClass("btn-info");
                     $(copy_button).html('<i class="fa fa-copy"></i>');
                     $(copy_button).attr('title', 'Copy Entry');
                     $(copy_button).css('margin-left', '20px');
                     $(copy_button).css('float', 'left');
                     copy_button.id = 'copy_'+event.id;

                     var copy_date = document.createElement("input");
                     copy_date.id = 'copy_date_'+event.id;
                     $(copy_date).datepicker({
                         dateFormat: 'yy-mm-dd',
                         onSelect: function(dateText, inst){
                             var id = this.id.split('_')[2];
                             $.ajax({
                                 url: '../copy_entry',
                                 data: {target: target_user, entry_id: id, date: dateText},
                                 dataType: 'json',
                                 success: function(new_event){
                                     console.log(new_event)
                                    // what should be the color of this event?
                                    var bg_color = '#e0fed0';
                                    if(new_event.activity.indexOf('non-billable') >= 0)
                                        bg_color = '#d0e5f0';

                                    var en = {
                                        title: new_event.name,
                                        start: new_event.date,
                                        comments: new_event.comments,
                                        activity: new_event.activity,
                                        backgroundColor: bg_color,
                                        textColor: '#000000',
                                        hours: new_event.hours,
                                        date: new_event.date,
                                        editable: true,
                                        id: new_event.id,
                                        project: new_event.name,
                                        activity_id: new_event.activity_id,
                                        project_id: new_event.project_id,
                                        changes: false
                                    };
                                     // add this to the events
                                     $('#calendar').fullCalendar('renderEvent', en);
                                 },
                                 error: function(){
                                     alert("Failed to copy your time entry.");
                                 }
                             });

                             // destroy the dialog
                             $('#dialog_'+event.id).remove();
                         }
                     });
                     $(copy_date).css('opacity', '0.0');
                     $(copy_date).css('height', '0px');

                     $(copy_button).click(function(){
                         $('#copy_date_'+this.id.split('_')[1]).datepicker('show');
                     });
                     $(button_row).append(copy_button);

                     // -- Delete Button
                     var delete_button = document.createElement("button");
                     $(delete_button).addClass("btn");
                     $(delete_button).addClass("btn-danger");
                     $(delete_button).css('margin-left', '20px');
                     $(delete_button).html('<i class="fa fa-trash"></i>');
                     $(delete_button).attr('title', 'Delete Entry');
                     delete_button.id = 'delete_'+event.id;
                     $(delete_button).click(function(){
                         if(confirm("Delete these hours?"))
                         {
                             var id = this.id.split('_')[1];
                             $.ajax({
                                 url: "../del_entry",
                                 data: {target: target_user, entry: id},
                                 dataType: 'text',
                                 success: function(){
                                     console.log("Entry deleted");
                                     $('#dialog_'+id).remove();
                                     $('#calendar').fullCalendar('removeEvents', [id]);

                                 },
                                 error: function(){
                                     alert("Something went wrong...please contact the system administrator!");
                                 }
                             })
                         }
                     });
                     $(button_row).append(delete_button);


                     $(button_row).append(copy_date);


                     $(dialog).append(button_row);


                     $(dialog).css('display', 'hidden');
                     //$(document).append(dialog);
                     $(dialog).dialog({
                         position: {
                             my: 'center top+20',
                             at: 'center top',
                             of: this
                         },
                         beforeClose: function(event, ui){
                             // check if we have settings to save
                             var id = this.id.split('_')[1];
                             if($('#calendar').fullCalendar('clientEvents', [id])[0].changes == false)
                                return true;

                             if(confirm("You have unsaved changes - discard?")) {
                                 $('#calendar').fullCalendar('clientEvents', [id])[0].changes = false;
                                 return true;
                             }
                             return false;
                         }
                     });

                },
                eventDrop: function(event, delta, revertFunc) {
                    if (!confirm("Move "+event.hours+" hours of '"+event.title + "' to " + event.start.format() +"?")) {
                        revertFunc();
                        return;
                    }

                    $.ajax({
                        url: '../update_entry_data',
                        data: {id: event.id, project: event.project, comments: event.comments, date: event.start.format(), hours: event.hours, target: $('#username').val(), activity: event.activity_id},
                        dataType: 'text',
                        success: function(){
                            console.log("Update successful");
                        },
                        error: function(){
                            alert("Failed to update entry.");
                        }

                    });
                },
                header: {
                    right: ''
                }
            });

			// get the holidays
			HOLIDAYS = data.holidays;

            // setup the user
			var user_empty = true;
			if(USER != '')
				user_empty = false;
			USER = data.user;
            if(target_user == '')
                target_user = USER;


			// setup the list of users, if we're a manager!
			var user_list = new Array();
			if(data.user_list != undefined)
				user_list = data.user_list;

			// do we have any users to display? (are we a manager?)
			if(user_list.length > 0)
			{
				// clear the list first!
				$('#user_dropdown').html('');

				// populate the drop-down menu
				for(var i = 0; i < user_list.length; i++)
				{
                    // create a new OPTION
                    var option = document.createElement("li");
                    var option_link = document.createElement("a");

                    option_link.value = user_list[i].login;
                    option_link.innerHTML = user_list[i].name;
                    if(user_list[i].login == target_user) {
                        console.log("FOUND: " + user_list[i].login);
                        $('#username').html(user_list[i].name);
                    }
                    $(option_link).css('cursor', 'pointer');
                    $(option_link).click(function(){
                        $('#username').html(this.innerHTML);
                        $('#username').val(this.value);
                        GetEntries();
                    });
                    $(option).append(option_link);

                    // add this option to our month select
                    $('#user_dropdown').append(option);



				}

				// show the drop-down menu
				$('#user_specific').removeClass('user_specific_hidden');
				$('#user_specific').addClass('user_specific_show');

				// add an "onchange" event
				$('#user').change(function(){
					GetEntries();
				});

			}

			// setup the "reset_user" changer
			$('#reset_user').click(function(){
				// set the drop-down menu to select "USER"
				$('#user option[value="'+USER+'"]').attr('selected', 'selected');

				// and update our entries!
				GetEntries();
			});
	
			// if our "user_empty" is true, this means we are at an initial load, 
			// so let's select ourselves in the drop-down menu
			if(user_empty && TARGET == '')
				$('#user option[value="'+USER+'"]').attr('selected', 'selected');
			if(TARGET != '')
				$('#user option[value="'+TARGET+'"]').attr('selected', 'selected');
			

			// setup our entries
			var entries = new Array();
			if(data.entries != undefined)
				entries = data.entries;
			// clear our entries
			$('#calendar').fullCalendar('removeEvents');
			for(var i = 0; i < entries.length; i++)
			{
                // what should be the color of this event?
                var bg_color = '#e0fed0';
                if(entries[i].activity.indexOf('non-billable') >= 0)
                    bg_color = '#d0e5f0';

				var en = {
                    title: entries[i].name,
                    start: entries[i].date,
                    comments: entries[i].comments,
                    activity: entries[i].activity,
                    backgroundColor: bg_color,
                    textColor: '#000000',
                    hours: entries[i].hours,
                    date: entries[i].date,
                    editable: true,
                    id: entries[i].id,
                    project: entries[i].name,
                    activity_id: entries[i].activity_id,
                    project_id: entries[i].project_id,
                    changes: false
                }
				$('#calendar').fullCalendar('renderEvent', en);

                // find this entry in "DAY_HOURS"
                var added = false;
                for(var j = 0; j < DAY_HOURS.length; j++)
                {
                    if(DAY_HOURS[j].date == entries[i].date) {
                        DAY_HOURS[j].hours += entries[i].hours;
                        added = true;
                        break;
                    }
                }
                if(!added)
                {
                    var new_date = {
                        date: entries[i].date,
                        hours: entries[i].hours
                    };
                    DAY_HOURS.push(new_date);
                }
			}

            // now color code each date with an entry to be a specific color
            for(var i = 0; i < DAY_HOURS.length; i++)
            {
                var hours = DAY_HOURS[i].hours;
                var color = '#D6FFC1';
                if(hours < EXPECTED_BILLABLE)
                    color = '#FFBEBE';

                var hour_display = document.createElement("DIV");
                $(hour_display).css('height', '100%');
                $(hour_display).css('width', '100%');
                $(hour_display).css('color', color);
                $(hour_display).css('text-align', 'center');
                $(hour_display).css('font-size', '60px');
                $(hour_display).css('position', 'absolute');
                $(hour_display).css('top', '0');
                $(hour_display).css('left', '0');
                $(hour_display).attr("title", "Total logged time: " + DAY_HOURS[i].hours);

                var hour_holder = document.createElement('div');
                $(hour_holder).html(DAY_HOURS[i].hours);
                $(hour_holder).css('position', 'relative');
                $(hour_holder).css('top', '50%');
                $(hour_holder).css('transform', 'translateY(-50%)');
                $(hour_display).append(hour_holder);

                var target = 'td.fc-day[data-date="'+DAY_HOURS[i].date+'"]';
                console.log("Adding hour display for " + DAY_HOURS[i].date);
                $(target).append(hour_display);
                $(target).css('position', 'relative');
            }
			$('#status_update').html('');
		},
		error: function(data){
			if(data.responseText == "I'm afraid I can't do that...")
			{
				document.write('<img src="/reports/media/img/no.png" />');
				document.close();
				return;
			}
			alert("Failed to retrieve your time entries.  Please contact the system administrator.");
		}
	});
}

var DAY_HOURS = [];

function SetupEntries()
{
	
	//-------------- Setup Datepicker objects for each of the Dates listed -------------------------------//
	$('.entry_date').each(function(){
		$(this).datepicker({
			dateFormat: "yy-mm-dd"
		});
	});

	//-------------------- Setup "onchange" events for all entry-specific elements --------------------------------------//
	// for projects
	$('.project_select').each(function(){
		$(this).change(function(){
			EntryChanged(this.parentNode.id.split('_')[1]);
		});
	});
	// for dates
	$('.entry_date').each(function(){
		$(this).change(function(){
			EntryChanged(this.parentNode.id.split('_')[1]);
		});
	});
	// for hours
	$('.entry_hours').each(function(){
                $(this).change(function(){
                        EntryChanged(this.parentNode.id.split('_')[1]);
                });
        });
	// for comments
	$('.comment').each(function(){
                $(this).change(function(){
                        EntryChanged(this.parentNode.id.split('_')[1]);
                });
        });
	// for issues
	$('.entry_issue').each(function(){
                $(this).change(function(){
                        EntryChanged(this.parentNode.id.split('_')[1]);
                });
        });
	// for activity
	$('.activity_select').each(function(){
                $(this).change(function(){
                        EntryChanged(this.parentNode.id.split('_')[1]);
                });
        });	

	//---------------------- Add functionality to our "Save" button ------------------------------//
	$('#save_button').click(function(){
		// gather all changes that need to be made
		var update_entries = [];
		for(var i = 0; i < UpdateEntries.length; i++)
		{
			var entry = new Entry();
			entry.id = UpdateEntries[i];
			entry.project = $('#project_'+UpdateEntries[i]).val();
			entry.date = $('#entry_date_'+UpdateEntries[i]).val();
			entry.hours = $('#entry_hours_'+UpdateEntries[i]).val();
			entry.comments = $('#comment_'+UpdateEntries[i]).val();
			entry.issue = $('#issue_'+UpdateEntries[i]).val();
			entry.activity = $('#activity_'+UpdateEntries[i]).val();

			// add this entry to the list to be updated
			update_entries.push(entry);
		}

		$.ajax({
			url: '../update_entries',
			data: {entries: JSON.stringify(update_entries)},
			contentType: "application/json; charset=utf-8",
			dataType: 'text',
			success: function(data){
				if(data == 'Error 97')
				{
					alert("You do not have permission to modify some of the entries you attempted to.\n\nBailing...");
					return;
				}
				if(data == 'Nothing to save')
					return;

				if(data == '200')
				{
					alert("Time entries saved!");
					for(var i = 0; i < UpdateEntries.length; i++)
					{
						$('#div_'+UpdateEntries[i]).toggleClass('time_entry_mod');
					}
					UpdateEntries = [];
					return;
				}
			},
			error: function(){
				console.log("Error");
			}
		});
	});
}


// List of entries that will need to be updated
var UpdateEntries = []


function EntryChanged(entry_id)
{
	// if we don't already have this entry in our list...
	if(UpdateEntries.indexOf(entry_id) < 0)
	{
		// add this entry to the list
		UpdateEntries.push(entry_id);

		// change the color of that DIV
		$("#div_"+entry_id).addClass('time_entry_mod');
	}
}

// day class
function Day(){
	this.day = null;
	this.month = null;
	this.year = null;
	this.weekday = null;
	this.hours = 0;
	this.holiday = false;
	this.holiday_name = null;
	this.class_name = null;

	// collection of entries
	this.entries = new Array();

	// how to display ourselves
	this.widget = function(){
		var d = document.createElement("td");
        $(d).addClass('day');

		// show our current date (if we have one)
		var dayd = document.createElement("DIV");
		dayd.className = 'day_display';
		var day_display = document.createElement("DIV");
		day_display.className = 'day_display_number';

		var day_hours = document.createElement("DIV");
		day_hours.className = 'hour_display';

		$(day_display).html(this.day);

		$(dayd).append(day_display);
		$(dayd).append(day_hours);

		if(this.day == null)
		    $(d).addClass('empty_day');

		
		$(d).append(dayd);

		// if we are a holiday...
		if(this.holiday)
		{
			var holiday = document.createElement("DIV");
			var date_to_check = this.year + '-' + this.month + '-' + this.day;
			holiday.className = 'holiday'; //this.class_name;
			$(holiday).html(this.holiday_name);
			$(d).append(holiday);
		}

		// for each entry, add it to the day
        var table = document.createElement("table");
        table.className = 'table';
        $(table).addClass("day-table");
        //$(table).addClass("table-striped");

		for(var i = 0; i < this.entries.length; i++)
		{
            var row = document.createElement("tr");

			var project_space = document.createElement("td");
			$(project_space).html(this.entries[i].project);
            $(project_space).addClass('project-entry');

			var hour_space = document.createElement("td");
			$(hour_space).html(this.entries[i].hours);
            $(hour_space).addClass('hour-entry');

            $(row).append(project_space);
            $(row).append(hour_space);

            if(this.entries[i].activity.indexOf('non-billable') >= 0)
                $(row).addClass('non-billable-row');

			// setup the "title"
			$(row).attr('title', this.entries[i].activity + ': '+this.entries[i].comments);

            $(table).append(row);

			// sum up the total hours for this day
			this.hours += parseFloat(this.entries[i].hours);
		}

        $(d).append(table);

		if(this.hours > 0)
			$(day_hours).html('Total Hours: ' + this.hours);

		return d;
	};
}

function CreateCalendar()
{
	// clear the project list
	$('#entry_list').html('');

	// get the first and last days of the month
	var firstDay = new Date($('#year_name').val(), $('#month_name').val() - 1, 1);
	var lastDay = new Date(firstDay.getFullYear(), firstDay.getMonth() + 1, 0);
	
	// keep track of which day we're on
	var current_weekday = firstDay.getDay();
	var current_date = firstDay.getDate();
	var total_days_generated = 0;
	
	// keep creating weeks until we end...
	while(current_date <= lastDay.getDate())
	{
		// create a new "week"
		var week = document.createElement('tr');
	
		// now create the next 7 days
		for(var i = 0; i < 7; i++)
		{
			var d = new Day();

			// is this a day of the month?
			if(current_weekday == total_days_generated && current_date <= lastDay.getDate())
			{
				d.day = current_date;
				d.month = $('#month_name').val();
				d.year = $('#year_name').val();
				d.weekday = i;

				var year = $('#year_name').val();
				var month = $('#month_name').val();
				var daten = current_date;
				if(month.length == 1)
					month = '0'+month;
				if(String(daten).length == 1)
					daten = '0'+daten;
				var date_to_check = $('#year_name').val() + '-' + month + '-' + daten;
	
				// is this a holiday?
				if(DateIsHoliday(date_to_check))
				{
					d.holiday = true;
					d.holiday_name = GetHolidayName(date_to_check);
					d.class_name = GetHolidayClassName(date_to_check);
				}

				d.entries = GetEntriesOnDate(date_to_check);
				// update the current date
				current_weekday++;
				current_date++;
			}
			total_days_generated++;
		
			var dwidget = d.widget();
			dwidget.id = 'day_'+i;
			$(week).append(dwidget);
			
		}
	
		// add this week to the calendar
		$('#entry_list').append(week);
		
	}

}

function GetEntriesOnDate(target_date)
{
	// matching list
	var match = new Array();
	for(var i = 0; i < EntryList.length; i++)
	{
		if(target_date == EntryList[i].date)
			match.push(EntryList[i]);
	}

	return match;
}

function DateIsHoliday(day)
{
	for(var i = 0; i < HOLIDAYS.length; i++)
	{
		if(String(day) == String(HOLIDAYS[i].date))
			return true;
	}
	return false;
}

// gets the name of the holiday based on the month
function GetHolidayName(holiday)
{
	// find the matching holiday
	for(var i = 0; i < HOLIDAYS.length; i++)
	{
		if(String(HOLIDAYS[i].date) == String(holiday))
			return HOLIDAYS[i].name;
	}	
}
// gets the name of the holiday based on the month
function GetHolidayClassName(holiday)
{
	var name = GetHolidayName(holiday);
	if('New Years Celebration' == name)
		return 'holiday_newyears';
	if('Good Friday' == name)
		return 'holiday_goodfriday';
	if('Memorial Day' == name)
		return 'holiday_memorialday';
	if('Independence Day' == name)
		return 'holiday_independenceday';
	if('Labor Day' == name)
		return 'holiday_laborday';
	if('Thanksgiving Break' == name)
		return 'holiday_thanksgiving';
	if('Christmas Break' == name)
		return 'holiday_christmas';
	if('Snow Day' == name)
		return 'holiday_snowday';
}
