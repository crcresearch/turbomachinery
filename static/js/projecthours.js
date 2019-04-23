var main_chart = null;

/****************
 * UpdateData
 * Makes an ajax call out to the server, passing in the selected project, date range, and selected users
 *  to gather weekly hours for each user logged for the project, then generates a line chart with that data.
 * @constructor
 */
function UpdateData(){
    // compute the dates
    var start_range = $('#date_range').val().split(' - ')[0];
	var end_range = $('#date_range').val().split(' - ')[1];

	// generate a list of selected users
    var user_list = new Array();
    $('[data-type="user-option"]').each(function(){
        if($(this).prop("checked")){
            user_list.push($(this).val())
        }
    });

    // make the call
    $.ajax({
        url: '/project_hour_entries',
        data: {
            project: $('#project_select').val(),
            start: start_range,
            end: end_range,
            users: user_list
        },
        dataType: 'json',
        success: function(data){
            GenerateChart(data);
        },
        error: function(){
            alert("Failed to get project hours.")
        }
    });
}


/**************
 * GenerateChart
 * Takes in data from the AJAX call from the server and generates a line chart using the HighCharts library.
 *
 * Called from: "UpdateData()"
 * @param data
 * @constructor
 */
function GenerateChart(data){
    main_chart = Highcharts.chart('chart', {

    title: {
        text: 'Project Hours By User'
    },

    subtitle: {
        text: 'Per Week'
    },

    yAxis: {
        title: {
            text: 'Hours Logged'
        }
    },
    legend: {
        layout: 'vertical',
        align: 'right',
        verticalAlign: 'middle'
    },
    xAxis: {
      categories: data.weeks
    },
    plotOptions: {
        series: {
            label: {
                connectorAllowed: false
            },
            // pointStart: 2010
        }
    },

    series: data.series,

    responsive: {
        rules: [{
            condition: {
                maxWidth: 500
            },
            chartOptions: {
                legend: {
                    layout: 'horizontal',
                    align: 'center',
                    verticalAlign: 'bottom'
                }
            }
        }]
    }

});
}


function UpdateUserList(){
    // get a list of users who have hours logged for this project
    $.ajax({
        url: '/get_users_for_project',
        data: {
            project: $('#project_select').val()
        },
        dataType: 'html',
        success: function(list){
            $('#user_list').html('').append(list);
        },
        error: function(){
            alert("Failed to refresh user list.");
        }
    })
}