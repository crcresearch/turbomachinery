// today's date
var today = new Date();

// expected hours
var expected = 0;

function GetOverview()
{
	// billable hours
			$("#billable_hours").html('Loading...');
			// non-billable
			$('#support_hours').html('Loading...');
			// total
			$('#total_hours').html('Loading...');
			// expected
			$('#expected').html('Loading...');
	$('#expected_chart').html('<h3 style="width: 100%; text-align: center;">Loading...</h3>');

	$.ajax({
		url: 'get_all_entries',
		data: {start: $('#date_range').val().split(' - ')[0], end: $('#date_range').val().split(' - ')[1], order: 'date', by: 'asc', include_manager: $('#include_manager_hours').prop('checked')},
		dataType: 'json',
		success: function(data){
			// billable hours
			$("#billable_hours").html(data.total);
			// non-billable
			$('#support_hours').html(data.support);
			// total
			$('#total_hours').html(parseFloat(data.support) + parseFloat(data.total));
			// expected
			$('#expected').html(data.weekdays);

			expected = data.billable;

			SetupExpected(data.entries);
		
		},
		error: function(){
			alert("Failed to get hourly summary!");
		}
	});
}

function SetupExpected(data)
{
	var entries = new Array();
	var nonbillable_entries = new Array();
	var expected_list = new Array();
	var dates = new Array();

	var next_date = '';
	var current_sum = 0;
	var current_nonbillable_sum = 0;
	for(var i = 0; i < data.length; i++)
	{
		if(String(data[i].date) == next_date)
		{
			if(data[i].activity.indexOf('on-billable') > 0){
				current_nonbillable_sum += data[i].hours;
			}
			else{
				current_sum += data[i].hours;
			}

		}
		else
		{
			if(current_sum != 0)
			{
				entries.push(current_sum);
				nonbillable_entries.push(current_nonbillable_sum);
				expected_list.push(expected);
				dates.push(next_date);
			}
			next_date = data[i].date;
			current_sum = 0;
			current_nonbillable_sum = 0;
			if(data[i].activity.indexOf('on-billable') > 0){
				current_nonbillable_sum = data[i].hours;
			}
			else{
				current_sum = data[i].hours;
			}
		}
	}
	if(data.length > 0)
	{
		entries.push(current_sum);
		expected_list.push(expected);
		dates.push(next_date);
	}

	$('#expected_chart').highcharts({
		chart: {
			zoomType: 'xy'
		},
		title: {
			text: ''
		},
		xAxis: [{
			categories: dates,
			labels: {
				rotation: -45,
				align: 'right'
			}
		}],
		yAxis: [{
			title: {
				text: 'Hours'
			}
		}],
		plotOptions: {
			series: {
				marker: {
					enabled: false
				}
			}
		},
		series: [{
			name: 'Billable Hours',
			color: '#76addb',
			type: 'column',
			data: entries
		},
			{
				name: "Non-Billable Hours",
				color: '#ff4f4f',
				type: 'column',
				data: nonbillable_entries
			}]
	});
}

function GetDistro()
{
	$('#chart').html('<h3 style="width: 100%; text-align: center;">Loading...</h3>');
	$.ajax({
		url: "get_all_distribution",
		data: {start_date: $('#date_range').val().split(' - ')[0], end_date: $('#date_range').val().split(' - ')[1], include_manager: $('#include_manager_hours').prop('checked')},
		dataType: 'json',
		success: function(data){
			SetupChart(data, "Time spent from "+$('#date_range').val().split(' - ')[0]+' to ' + $('#date_range').val().split(' - ')[1]);
		},
		error: function(){
			alert("Failed to get time distribution!");
		}
	});	
}

var PROJECT_ENTRIES;
var TOTAL_HOURS = 0;

function GetRandomColors(length){
	var colors = [];
	for(var i = 0; i < length; i++){
		var new_color = randomColor();
		while(colors.indexOf(new_color) >= 0){
			new_color = randomColor();
		}
		colors.push(new_color);
	}
	return colors;
}

function SetupChart(data, title)
{
	// var total = data.total;
	// var entries = data.entries;
	// PROJECT_ENTRIES = entries;
	// TOTAL_HOURS = total;
    //
	// var data_list = new Array();
    //
	// for(var i = 0; i < entries.length; i++)
	// {
	// 	var entry = new Array(entries[i].name, ((entries[i].hours / total) * 100), entries[i].hours);
	// 	data_list.push(entry);
	// }
    //
	// var main_chart = new Highcharts.Chart({
	// 	chart: {
     //                    renderTo: 'chart',
     //                    plotBackgroundColor: null,
     //                    plotBorderWidth: null,
     //                    plotShadow: false,
     //                    backgroundColor: 'rgba(255, 255, 255, 0.0)'
     //            },
     //            title: {
     //                    text: ''
     //            },
     //            tooltip: {
     //                    formatter: function(){
     //                            for(var i = 0; i < data_list.length; i++)
     //                            {
     //                                    if(data_list[i][0] == this.point.name)
     //                                            return '<b>'+this.point.name + '</b>: '+parseFloat(Math.round(data_list[i][1] * 100)/100).toFixed(1) + '%<br>'+data_list[i][2] + ' hours';
     //                            }
     //                            return this.point.name + ': ' + this.point.percentage + '%';
     //                    }
     //            },
     //            plotOptions:{
     //                    pie: {
     //                            allowPointSelect: true,
     //                            cursor: 'pointer',
     //                            dataLabels: {
     //                                    enabled: true,
     //                                    color: '#000000',
     //                                    connectorColor: '#000000',
     //                                    format: '<b>{point.name}</b>: {point.percentage:.1f} %'
     //                            }
     //                    }
     //            },
     //            series: [{
     //                    type: 'pie',
     //                    name: 'Time Distribution',
     //                    data: data_list
     //            }],
    //
	// });

	var categories = [];
	var chart_data = [];
	var parent_data = [], child_data = [];
	// var chart_colors = GetRandomColors(data.entries.length);
	var chart_colors = Highcharts.getOptions().colors;
	while(chart_colors.length < data.entries.length){
		var next_colors = Highcharts.getOptions().colors;
		chart_colors = chart_colors.concat(next_colors);
	}
	var brightness;

	// setup the categories (these are the project names)
	for(var i = 0; i < data.entries.length; i++){
		categories.push(data.entries[i].name);
	}

	// now setup the data
	for(var i = 0; i < data.entries.length; i++){
		// create a new data entry
		var entry = {};
		entry.y = data.entries[i].percent;
		entry.hours = data.entries[i].total_hours;
		entry.color = chart_colors[i];
		entry.drilldown = {};
		entry.drilldown.name = data.entries[i].name + ' - Sub-projects';
		entry.drilldown.categories = [];
		entry.drilldown.data = [];
		entry.drilldown.hours = [];
		for(var j = 0; j < data.entries[i].subprojects.length; j++) {
			entry.drilldown.categories.push(data.entries[i].subprojects[j].name);
			entry.drilldown.data.push(data.entries[i].subprojects[j].percent);
			entry.drilldown.hours.push(data.entries[i].subprojects[j].total_hours);
			entry.drilldown.color = chart_colors[i];
		}

		chart_data.push(entry);
	}

	console.log(chart_data);

	// build the data arrays (??) (re-organize, set brightness...cause apparently you have to do this by hand...DUMB.
	for(var i = 0; i < chart_data.length; i++){
		parent_data.push({
			name: categories[i],
			y: chart_data[i].y,
			hours: chart_data[i].hours,
			color: chart_data[i].color
		});

		// add sub-version data
		var drillDataLen = chart_data[i].drilldown.data.length;
		for(var j = 0; j < drillDataLen; j += 1){
			brightness = 0.2 - (j / drillDataLen) / 5;
			child_data.push({
				name: chart_data[i].drilldown.categories[j],
				y: chart_data[i].drilldown.data[j],
				hours: chart_data[i].drilldown.hours[j],
				color: Highcharts.Color(chart_data[i].color).brighten(brightness).get()
			});
		}
	}

	// create the chart!
	Highcharts.chart('chart', {
		chart: {
			type: 'pie'
		},
		title: {
			text: title
		},
		exporting: {
			sourceWidth: 1400,
			sourceHeight: 900
		},
		plotOptions: {
			pie: {
				shadow: false,
				center: ['50%', '50%']
			}
		},
		tooltip: {
			formatter: function(){
				return '<b>' + this.point.name + '</b>: ' + this.point.hours + ' hours'
			}
		},
		series: [{
			name: 'Project',
			data: parent_data,
			size: '60%',
			dataLabels: {
				formatter: function() {
					return this.y > 5 ? this.point.name : null;
				},
				color: '#ffffff',
				distance: -30
			}
		}, {
			name: 'Sub-Project',
			data: child_data,
			size: '80%',
			innerSize: '60%',
			dataLabels: {
				formatter: function(){
					return this.y > 1 ? '<b>' + this.point.name + ':</b>' + this.point.hours + ' hours' : null;
				}
			},
			id: 'subprojects'
		}],
		responsive: {
			rules: [{
            condition: {
                maxWidth: 400
            },
            chartOptions: {
                series: [{
                    id: 'subprojects',
                    dataLabels: {
                        enabled: false
                    }
                }]
            }
        }]
		}
	});
}

