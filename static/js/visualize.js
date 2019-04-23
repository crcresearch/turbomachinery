function init()
{
	// add some functionality to our elements
	$('#generate_view').click(function(){
		GenerateProgrammersView();
	});

	var now = new Date();
	var day = ("0" + now.getDate()).slice(-2);
	var month = ("0" + (now.getMonth() + 1)).slice(-2);

	var first_of_month = now.getFullYear()+"-"+(month)+"-01";
	var today = now.getFullYear()+"-"+(month)+"-"+(day);
	$('#start_date').val(first_of_month);
	$('#end_date').val(today);

	$('#start_date').datepicker({
		dateFormat: 'yy-mm-dd'
	});
	$('#end_date').datepicker({
		dateFormat: 'yy-mm-dd'
	});

	GenerateProgrammersView();

	//UpdateEntityList();

}


function GenerateProgrammersView()
{
	$.ajax({
		url: "../get_distribution",
		data: {start_date: $('#start_date').val(), end_date: $('#end_date').val()},
		dataType: 'json',
		success: function(data){
			SetupChart(data, "Your Time Distribution");
		},
		error: function(){
			alert("Failed to get distribution");
		}
	});
}

var main_chart = null;
var data_list = new Array();


function SetupChart(data, title)
{
	// get the total and entries
	var total = data.total;
	var entries = data.entries;

	// create a 2D array of our information we need
	data_list = new Array();

	for(var i = 0; i < entries.length; i++)
	{
		var entry = {
			name: entries[i].name,
			y: entries[i].hours
		}; //new Array(entries[i].name, ((entries[i].hours / total) * 100), entries[i].hours);
		data_list.push(entry);
	}

	var chart_title = title;

	// create the piechart!
	main_chart = new Highcharts.Chart({
		chart: {
			renderTo: 'chart',
			plotBackgroundColor: null,
			plotBorderWidth: null,
			plotShadow: false,
			backgroundColor: 'rgba(255, 255, 255, 0.0)'
		},
		title: {
			text: chart_title
		},
		tooltip: {
			formatter: function(){
				for(var i = 0; i < data_list.length; i++)
				{
					if(data_list[i][0] == this.point.name)
						return '<b>'+this.point.name + '</b>: '+parseFloat(Math.round(data_list[i][1] * 100)/100).toFixed(1) + '%<br>'+data_list[i][2] + ' hours';
				}
				return this.point.name + ': ' + this.point.percentage + '%';
			}
			//pointFormat: '{series.name}: <b>{point.percentage:.1f}%</b>'
		},
		plotOptions:{
			pie: {
				allowPointSelect: true,
				cursor: 'pointer',
				dataLabels: {
					enabled: true,
					color: '#000000',
					connectorColor: '#000000',
					format: '<b>{point.name}</b>: {point.y} hours ({point.percentage:.1f} %)'
				}
			}
		},
		series: [{
			type: 'pie',
			name: 'Time Distribution',
			data: data_list
		}]
	});
}

function ClearChart()
{
	// clear the chart area
	$('#chart').html('Click "View" to update chart');

	// clear the budget area
	$('#budget_holder').css('display', 'none');
	$('#no_budget').css('display', 'none');
}
