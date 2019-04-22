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
	this.logas = '';
}

// Main function that is called once the page is loaded.
// This function selects the previous month for the user automatically.
// It also sets an "onchange" event for each checkbox - this is used to keep track, using local storage, the selected items.
function init()
{
	// make a call to get all of our info we need to fill out our time entries and options
	// $.ajax({
	// 	url: '../get_dates',
	// 	dataType: "json",
	// 	success: function(data){
			// setup the month list
			// var months = data.months;
			// for(var i = 0; i < months.length; i++)
			// {
			// 	// create a new OPTION
			// 	var option = document.createElement("li");
            //     var option_link = document.createElement("a");
			//
			// 	option_link.value = months[i].number;
			// 	option_link.innerHTML = months[i].name;
            //     option_link.name = 'month';
            //     $(option_link).css('cursor', 'pointer');
            //     $(option_link).click(function(){
            //         $('#month_name').html(this.innerHTML);
            //         $('#month_name').val(this.value);
            //         GetEntries();
            //     });
            //     $(option).append(option_link);
			//
			// 	// add this option to our month select
			// 	$('#month_dropdown').append(option);
			// }
			//
			// // setup the year list
			// var years = data.years;
			// for(var i = 0; i < years.length; i++)
			// {
			// 	// create a new OPTION
			// 	var option = document.createElement("li");
            //     var option_link = document.createElement("a");
			//
			// 	option_link.value = years[i].year;
			// 	option_link.innerHTML = years[i].year;
            //     $(option_link).css('cursor', 'pointer');
            //     $(option_link).click(function(){
            //         $('#year_name').html(this.innerHTML);
            //         $('#year_name').val(this.value);
            //         GetEntries();
            //     });
            //     $(option).append(option_link);
			//
			// 	// add this option to our month select
			// 	$('#year_dropdown').append(option);
			// }
			//
			// // add one more year (so we can look at next year if desired)
            // // create a new OPTION
            // var option = document.createElement("li");
            // var option_link = document.createElement("a");
			//
            // option_link.value = years[years.length-1].year + 1;
            // option_link.innerHTML = years[years.length-1].year + 1;
            // $(option_link).css('cursor', 'pointer');
            // $(option_link).click(function(){
            //     $('#year_name').html(this.innerHTML);
            //     $('#year_name').val(this.value);
            //     GetEntries();
            // });
            // $(option).append(option_link);
			//
            // // add this option to our month select
            // $('#year_dropdown').append(option);
	Establish();


	//---------------------- Add functionality to our "Add Entry" button -------------------------//
	$('#add_button').click(function(){
		AddEntry();
	});

	//---------------------- Add functionality to our "Save" button ------------------------------//
	$('#save_button').click(function(){
		// gather all changes that need to be made
		var update_entries = [];
		for(var i = 0; i < UpdateEntries.length; i++)
		{
			var entry = new Entry();
			// are we working with a new entry, or existing?
			if(UpdateEntries[i].indexOf("new") >= 0)
			{
				// new entry!
				// get the number of our "new" entry
				var new_entry = UpdateEntries[i].split('_')[2];
				entry.id = 'new_entry';
				entry.project = $('#project_new_'+new_entry).val();
				entry.date = $('#entry_date_new_'+new_entry).val();
				entry.hours = $('#entry_hours_new_'+new_entry).val();
				entry.comments = $('#comment_new_'+new_entry).val();
				entry.issue = $('#issue_new_'+new_entry).val();
				entry.activity = $('#activity_new_'+new_entry).val();
				entry.logas = $('#logas_new_'+new_entry).val();
			}
			else
			{
				// existing entry!
				entry.id = UpdateEntries[i];
				entry.project = $('#project_'+UpdateEntries[i]).val();
				entry.date = $('#entry_date_'+UpdateEntries[i]).val();
				entry.hours = $('#entry_hours_'+UpdateEntries[i]).val();
				entry.comments = $('#comment_'+UpdateEntries[i]).val();
				entry.issue = $('#issue_'+UpdateEntries[i]).val();
				entry.activity = $('#activity_'+UpdateEntries[i]).val();
				entry.logas = $('#logas_'+UpdateEntries[i]).val();
			}

			// add this entry to the list to be updated
			update_entries.push(entry);
		}

		$.ajax({
			url: '../update_entries',
			data: {entries: JSON.stringify(update_entries), target: $('#username').val()},
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
					GetEntries();
					return;
				}
			},
			error: function(){
				alert("Failed to save entries.");
			}
		});
	});


	// 	},
	// 	error: function(){
	// 		alert("Could not get time entries.  Please contact the system administrator.");
	// 	}
	// });

}

function Establish()
{
	// check if we want to look up a specific user...
	if(window.location.href.indexOf('=') > 0)
	{
		TARGET = window.location.href.split('=')[1];
	}

	//------------- Setting up Current Month ------------------//
	//------------- Setting up Current Month ------------------//
	// var now = new Date();
	// var this_year = now.getFullYear();
	// var this_month = now.getMonth() + 1;
	//
	// // now select this month from the drop-down list
    // // find the month for this month
    // $('a[name="month"]').each(function(){
    //    if($(this).val() == this_month)
    //    {
    //        $('#month_name').html($(this).html());
    //        $('#month_name').val(this.value);
    //    }
    // });

	//$('#month_name').html(this_month);

	// and now select this year
	// $('#year_name').html(this_year);
    // $('#year_name').val(this_year);


	//--------------- Setup Onchange Events for Month/Year Selections ----------------------------------//
	// $('#month_name').change(function(){
	// 	GetEntries();
	// });
	//
	// $('#year_name').change(function(){
	// 	GetEntries();
	// });

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

// list of projects for this coder
var PROJECT_LIST = new Array();

// list of activities
var ACTIVITY_LIST = new Array();

// list of "log as" options
var LOGAS_LIST = new Array();

function GetEntries()
{
	// make sure we clear our DIV
	$('#entry_list').html('');

	// which target should we use?
	var target_user = $('#username').val();
	if(TARGET != '')
	{
		target_user = TARGET;
	}

	// now that we have our date setup, let's get our entries!
	var start_range = $('#date_range').val().split(' - ')[0];
	var end_range = $('#date_range').val().split(' - ')[1];
	$.ajax({
		url: '../get_entries',
		data: {start: start_range, end: end_range, target: target_user, order: ORDER_BY, by: ORDER},
		dataType: 'json',
		success: function(data){
			// first check if we passed the "tests"
			if(data == "I'm afraid I can't do that...")
			{
				document.write('<img src="/reports/media/img/no.png" />');
				document.close();
				return;
			}
			// quick!  grab the project list and activity list!!
			PROJECT_LIST = data.projects;
			ACTIVITY_LIST = data.activities;
			LOGAS_LIST = data.logas;

			// did we get any back?
			if(data.result == 'No Entries')
			{
				$('#entry_list').html('<div style="width: 100%; padding-top: 20px; text-align: center;">No Entries</div>');
				return;
			}

			// setup the total hours
			var total_hours = data.total;
			$('#billable_hours').html(total_hours);

			// setup the non-billable hours
			var support = data.support;
			$('#support_hours').html(support);

			// setup total
			$('#total_hours').html(parseFloat(support) + parseFloat(total_hours));


			// setup the user
			var user_empty = true;
			if(USER != '')
				user_empty = false;
			USER = data.user;
            if(target_user == '')
                target_user = USER;

			// setup expected hours
			var expected = data.weekdays;
			$('#expected').html(expected);

			// setup the manager's link (if there is one)
			$('#managers_link').html(data.managers_link);

			// setup the list of users, if we're a manager!
			var user_list = data.user_list;

			// do we have any users to display? (are we a manager?)
			if(user_list.length > 0 )
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
				TARGET = USER;

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
			entries = data.entries;


			for(var i = 0; i < entries.length; i++)
			{
				// create a new row
				var div = document.createElement("tr");
				div.id = "row_"+entries[i].id;

				//------ Project Dropdown ---------//
                var proj_cell = document.createElement("td");
				var proj = document.createElement("SELECT");
				proj.id = 'project_'+entries[i].id;
				proj.className = 'project_select';
                $(proj).addClass('form-control');
			
				// options...
				for(var j = 0; j < data.projects.length; j++)
				{
					// create a new option
					var option = document.createElement("OPTION");
					option.value = data.projects[j].id;
					option.innerHTML = data.projects[j].name;
				
					// if this project is the same that our entry is assigned to, select it.
					if(option.value == entries[i].project)
						option.selected = "SELECTED";

					// add this option to our select
					$(proj).append(option);
				}

				// add some functionality to the dropdown (if they select "MyTimeOff", then
				// the corresponding "Activity" should only be "Support (Nonbillable)")
				$(proj).change(function(){
					var id = this.id.split('_')[1];
					var project_id = $(this).val();
					$.ajax({
						url: '../get_activities?project='+project_id,
						dataType: 'json',
						success: function(data){
							// what is the currently selected activity?
							var selected_activity = $('#activity_'+id+' option:selected').html();
							// clear the list
							$('#activity_'+id).html('');
							for(var i = 0; i < data.length; i++)
							{
								// create a new option
								var option = document.createElement('option');
								$(option).val(data[i].id);
								$(option).html(data[i].name);

								// do we select it?
								if(data[i].name == selected_activity)
									$(option).attr('selected', 'selected');

								// add it to our list!
								$('#activity_'+id).append(option);
							}
						},
						error: function(){
							console.log("Failed to get activities for this project.");
						}
					});
				});

				// add this drop-down to the div
				$(proj_cell).append(proj);
                $(div).append(proj_cell);

				//---------- Entry Date ------------//
                var day_cell = document.createElement("td");
				var day = document.createElement("INPUT");
				day.type = "text";
				day.className = "entry_date";
				day.value = entries[i].date;
				day.id = "entry_date_"+entries[i].id;

				// add it to the div
                $(day_cell).append(day);
				$(div).append(day_cell);


				//----------- Hours ------------//
                var hours_cell = document.createElement("td");
				var hours = document.createElement("INPUT");
				hours.type = "text";
				hours.className = "entry_hours";
				hours.value = entries[i].hours;
				hours.id = "entry_hours_"+entries[i].id;
			
				// add it to the div
                $(hours_cell).append(hours);
				$(div).append(hours_cell);


				//----------- Comments ------------//
                var comments_cell = document.createElement("td");
				var comments = document.createElement("INPUT");
				comments.type = "text";
				comments.className = "comment";
				comments.value = entries[i].comments;
				comments.id = "comment_"+entries[i].id;
			
				// add it to the div
                $(comments_cell).append(comments);
				$(div).append(comments_cell);
	
				
				//----------- Issue ------------//
                var issue_cell = document.createElement("td");
				var issue = document.createElement("INPUT");
				issue.type = "text";
				issue.className = "entry_issue";
				issue.value = entries[i].issue;
				issue.id = "issue_"+entries[i].id;
			
				// add it to the div
                $(issue_cell).append(issue);
				$(div).append(issue_cell);
		

				//----------- Issue Link -------//
				var link = document.createElement("SPAN");
				link.className = "issue_link";
				if(issue.value != '')
					link.innerHTML = '<a href="https://redmine.crc.nd.edu/redmine/issues/'+entries[i].issue+'" target="_blank">&rarr;</a>';
				
				// add it to the div
                $(issue_cell).append(link);

				//------------ Activity ------------//
                var activity_cell = document.createElement("td");
				var act = document.createElement("SELECT");
				act.id = "activity_"+entries[i].id;
				act.className = "activity_select";
			
				// options...get the activities of the given project
				//
				for(var j = 0; j < data.activities.length; j++)
				{
					// new option
					var option = document.createElement("OPTION");
					option.value = data.activities[j].id;
					option.innerHTML = data.activities[j].name;
					
					// if this activity is the same that the entry was logged as, select it
					if(option.innerHTML == entries[i].activity)
						option.selected = "SELECTED";

					// add this option to our drop-down menu
					$(act).append(option);
				}
				
				// add the activity drop-down to our div
                $(activity_cell).append(act);
				$(div).append(activity_cell);
		
				//--------- Log As ----------------//
                var logas_cell = document.createElement("td");
				var logas = document.createElement("SELECT");
				logas.id = "logas_"+entries[i].id;
				logas.className = "logas_select";

				// options...
				for(var j = 0; j < LOGAS_LIST.length; j++)
				{
					// new option
					var option = document.createElement("OPTION");
					option.value = LOGAS_LIST[j].name;
					option.innerHTML = LOGAS_LIST[j].name;

					if(option.innerHTML == entries[i].logas)
						option.selected = "SELECTED";
	
					// add this option to our drop-down menu
					$(logas).append(option);
				}

				// add the "log as" drop-down to our div
                $(logas_cell).append(logas);
				$(div).append(logas_cell);


				//-------- Delete ---------//
                var delete_cell = document.createElement("td");
				var del = document.createElement("button");
				del.id = "delete_"+entries[i].id;
				del.className = "delete_button";
				$(del).html("Delete");
			
				// add the delete button to our div
                $(delete_cell).append(del);
				$(div).append(delete_cell);

				// add this div to our project list
				$('#entry_list').append(div);

			}
			
			// setup other widgets, etc
			SetupEntries();
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
			EntryChanged(this.parentNode.parentNode.id.split('_')[1]);
		});
	});
	// for dates
	$('.entry_date').each(function(){
		$(this).change(function(){
			EntryChanged(this.parentNode.parentNode.id.split('_')[1]);
		});
	});
	// for hours
	$('.entry_hours').each(function(){
                $(this).change(function(){
                        EntryChanged(this.parentNode.parentNode.id.split('_')[1]);
                });
        });
	// for comments
	$('.comment').each(function(){
                $(this).change(function(){
                        EntryChanged(this.parentNode.parentNode.id.split('_')[1]);
                });
        });
	// for issues
	$('.entry_issue').each(function(){
                $(this).change(function(){
                        EntryChanged(this.parentNode.parentNode.id.split('_')[1]);
                });
        });
	// for activity
	$('.activity_select').each(function(){
                $(this).change(function(){
                        EntryChanged(this.parentNode.parentNode.id.split('_')[1]);
                });
        });

	// for log as
	$('.logas_select').each(function(){
		$(this).change(function(){
			EntryChanged(this.parentNode.parentNode.id.split('_')[1]);
		});
	});

	// for delete
	$('.delete_button').each(function(){
		$(this).click(function(){
			DeleteEntry(this.parentNode.parentNode.id);
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

		// change the color of that DIV (if it's not a new one)
		if(entry_id.indexOf('new') < 0)
			$("#row_"+entry_id).addClass('time_entry_mod');
	}
}

// Adds a new entry to the table - a way to log time for any project...all one one page! :D
function AddEntry()
{
	// create a new DIV
	var div = document.createElement("tr");
	div.className = 'new_entry';
	div.id = "div_new_"+UpdateEntries.length;

	//------ Project Dropdown ---------//
    var proj_cell = document.createElement("th");
	var proj = document.createElement("SELECT");
	proj.id = 'project_new_'+UpdateEntries.length;
	proj.className = 'project_select';
	$(proj).addClass('form-control');
			
	// options...
	for(var j = 0; j < PROJECT_LIST.length; j++)
	{
		// create a new option
		var option = document.createElement("OPTION");
		option.value = PROJECT_LIST[j].id;
		option.innerHTML = PROJECT_LIST[j].name;
		
		// add this option to our select
		$(proj).append(option);
	}

	// add some functionality to the dropdown (if they select "MyTimeOff", then
	// the corresponding "Activity" should only be "Support (Nonbillable)")
	$(proj).change(function(){
		// get a list of activities for this project
		var id = this.id.split('_')[2];
		$.ajax({
			url: '../get_activities?project='+$(this).val(),
			dataType: 'json',
			success: function(data){
				// update the list of options in our corresponding
				// activity list!
				// first by erasing the contents of this list...
				// (but remember what the selected one was!)
				var selected_option = $("#activity_new_"+id+" option:selected").html();
				$('#activity_new_'+id).html('');
				for(var i = 0; i < data.length; i++)
				{
					// create a new option!
					var option = document.createElement('option');
					$(option).val(data[i].id);
					$(option).html(data[i].name);
			
					// was this the selected option?
					if(data[i].name == selected_option)
						$(option).attr('selected', 'selected');
			
					// add it to the list!
					$('#activity_new_'+id).append(option);
				}
			},
			error: function(){
				console.log("Failed to get activities for this project.");
			}
		});
	});



	// add this drop-down to the div
    $(proj_cell).append(proj);
	$(div).append(proj_cell);
	

	//---------- Entry Date ------------//
    var day_cell = document.createElement("th");
	var day = document.createElement("INPUT");
	day.type = "text";
	day.className = "entry_date";
	$(day).addClass('form-control');
	var now = new Date();
	day.value = now.toISOString().split('T')[0];
	day.id = "entry_date_new_"+UpdateEntries.length;

	$(day).datepicker({
		dateFormat: "yy-mm-dd"
	});

	// add it to the div
    $(day_cell).append(day);
	$(div).append(day_cell);


	//----------- Hours ------------//
    var hour_cell = document.createElement("th");
	var hours = document.createElement("INPUT");
	hours.type = "text";
	hours.className = "entry_hours";
	$(hours).addClass('form-control');
	hours.value = '';
	hours.id = "entry_hours_new_"+UpdateEntries.length;
		
	// add it to the div
    $(hour_cell).append(hours);
	$(div).append(hour_cell);

	//----------- Comments ------------//
    var comments_cell = document.createElement("th");
	var comments = document.createElement("INPUT");
	comments.type = "text";
	comments.className = "comment";
	$(comments).addClass('form-control');
	comments.value = "";
	comments.id = "comment_new_"+UpdateEntries.length;
	
	// add it to the div
    $(comments_cell).append(comments);
	$(div).append(comments_cell);
					
	//----------- Issue ------------//
    var issue_cell = document.createElement("th");
	var issue = document.createElement("INPUT");
	issue.type = "text";
	issue.className = "entry_issue";
	$(issue).addClass('form-control');
	issue.value = '';
	issue.id = "issue_new_"+UpdateEntries.length;
	
	// add it to the div
    $(issue_cell).append(issue);
	$(div).append(issue_cell);
	
	// empty issue link (to keep things lined up)
	var link = document.createElement("SPAN");
	link.className = "issue_link";
				
	// add it to the div
	$(issue_cell).append(link);

	//------------ Activity ------------//
    var activity_cell = document.createElement("th");
	var act = document.createElement("SELECT");
	act.id = "activity_new_"+UpdateEntries.length;
	act.className = "activity_select";
	$(act).addClass('form-control');
	
	// options...
	for(var j = 0; j < ACTIVITY_LIST.length; j++)
	{
		// new option
		var option = document.createElement("OPTION");
		option.value = ACTIVITY_LIST[j].id;
		option.innerHTML = ACTIVITY_LIST[j].name;
			
		// add this option to our drop-down menu
		$(act).append(option);
	}

	// add the activity drop-down to our div
    $(activity_cell).append(act);
	$(div).append(activity_cell);


	//--------- Log As ----------------//
    var logas_cell = document.createElement("th");
	var logas = document.createElement("SELECT");
	logas.id = "logas_new_"+UpdateEntries.length;
	logas.className = "logas_select";
	$(logas).addClass('form-control');

	// options...
	for(var j = 0; j < LOGAS_LIST.length; j++)
	{
		// new option
		var option = document.createElement("OPTION");
		option.value = LOGAS_LIST[j].name;
		option.innerHTML = LOGAS_LIST[j].name;

		// add this option to our drop-down menu
		$(logas).append(option);
	}	

	// add the "log as" drop-down to our div
    $(logas_cell).append(logas);
	$(div).append(logas_cell);


	//-------- Delete ---------//
    var delete_cell = document.createElement("th");
	var del = document.createElement("button");
	del.id = "delete_new_"+UpdateEntries.length;
	del.className = "delete_button";
	$(del).html("Delete");
	$(del).click(function(){
		DeleteEntry(this.parentNode.parentNode.id)
	});	
		
	// add the delete button to our div
    $(delete_cell).append(del);
	$(div).append(delete_cell);

	// add this div to our project list
	$('#entry_list').append(div);

	// add this div to our UpdateEntries list
	UpdateEntries.push(div.id);

}

function DeleteEntry(id)
{
	// is this one that hasn't been submitted yet?
	if(id.split('_')[1] == 'new')
	{
		// then we simply remove it from the display and updated entries
		var index = UpdateEntries.indexOf(id);
		UpdateEntries.splice(index, 1);
		$('#'+id).remove();
	}

	// if not, then we send a request to delete this entry!
	if(id.split('_')[1] != 'new')
	{
		$.ajax({
			url: '../del_entry?entry='+id.split('_')[1],
			dataType: 'text',
			success: function(data){
				if(data == '200')
				{
					alert("Time entry removed!");
					GetEntries();			
				}
				if(data == 'Error 97')
				{
					alert("You do not have permission to delete that data entry.");
				}
			},
			error: function(){
				alert("Failed to remove entry.");
			}
		});
	}
}
