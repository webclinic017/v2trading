
API_KEY = localStorage.getItem("api-key")

// Iterate through each element in the
// first array and if some of them
// include the elements in the second
// array then return true.
function findCommonElements3(arr1, arr2) {
return arr1.some(item => arr2.includes(item))
}

//KEY shortcuts
Mousetrap.bind('e', function() { 
    $( "#button_edit" ).trigger( "click" );
});
Mousetrap.bind('a', function() { 
    $( "#button_add" ).trigger( "click" );
});
Mousetrap.bind('d', function() { 
    $( "#button_dup" ).trigger( "click" );
});
Mousetrap.bind('c', function() { 
    $( "#button_copy" ).trigger( "click" );
});
Mousetrap.bind('r', function() { 
    $( "#button_run" ).trigger( "click" );
});
Mousetrap.bind('p', function() { 
    $( "#button_pause" ).trigger( "click" );
});
Mousetrap.bind('s', function() { 
    $( "#button_stop" ).trigger( "click" );
});
Mousetrap.bind('j', function() { 
    $( "#button_add_json" ).trigger( "click" );
});
Mousetrap.bind('x', function() { 
    $( "#button_delete" ).trigger( "click" );
});

//on button
function store_api_key(event) {
    key = document.getElementById("api-key").value;
    localStorage.setItem("api-key", key);
    API_KEY = key;
}

function get_status(id) {
    var status = "stopped"
    runnerRecords.rows().iterator('row', function ( context, index ) {
        var data = this.row(index).data();
        //window.alert(JSON.stringify(data))
        if (data.id == id) {
            //window.alert("found");
            if ((data.run_mode) == "backtest") { status_detail = data.run_mode}
            else { status_detail = data.run_mode + " | " + data.run_account}
            if (data.run_paused == null) {
                status = "running | "+ status_detail
            }
            else {
                status = "paused | "+ status_detail
            }}
            //window.alert("found") }
    });
    return status
}

function is_running(id) {
    var running = false
    runnerRecords.rows().iterator('row', function ( context, index ) {
        var data = this.row(index).data();
        //window.alert(JSON.stringify(data))
        if (data.id == id) {
            running = true    
        }
            //window.alert("found") }
    });
    return running
}
    // alert(JSON.stringify(stratinRecords.data()))
    // arr = stratinRecords.data()
    // foreach(row in arr.rows) {
    //     alert(row.id)
    // }

    // //let obj = arr.find(o => o.id2 === '2');
    // //console.log(obj);
    // //alert(JSON.stringify(obj))




$(document).ready(function () {
    //reaload hlavni tabulky

    stratinRecords.ajax.reload();
    runnerRecords.ajax.reload();

    $('#trade-timestamp').val(localStorage.getItem("trade_timestamp"));
    $('#trade-count').val(localStorage.getItem("trade_count"));
    $('#trade-symbol').val(localStorage.getItem("trade_symbol"));
    $('#trade-minsize').val(localStorage.getItem("trade_minsize"));
    $('#trade-filter').val(localStorage.getItem("trade_filter"));


    //disable buttons (enable on row selection)
    $('#button_pause').attr('disabled','disabled');
    $('#button_stop').attr('disabled','disabled');
    $('#button_edit').attr('disabled','disabled');
    $('#button_dup').attr('disabled','disabled');
    $('#button_copy').attr('disabled','disabled');
    $('#button_delete').attr('disabled','disabled');
    $('#button_run').attr('disabled','disabled');

    //selectable rows in stratin table
    $('#stratinTable tbody').on('click', 'tr', function () {
        if ($(this).hasClass('selected')) {
            $(this).removeClass('selected');
            $('#button_dup').attr('disabled','disabled');
            $('#button_copy').attr('disabled','disabled');
            $('#button_edit').attr('disabled','disabled');
            $('#button_delete').attr('disabled','disabled');
            $('#button_run').attr('disabled','disabled');
        } else {
            stratinRecords.$('tr.selected').removeClass('selected');
            $(this).addClass('selected');
            $('#button_dup').attr('disabled',false);
            $('#button_copy').attr('disabled',false);
            $('#button_edit').attr('disabled',false);
            $('#button_delete').attr('disabled',false);
            $('#button_run').attr('disabled',false);
        }
    });

    //selectable rows runners Table
    $('#runnerTable tbody').on('click', 'tr', function () {
        if ($(this).hasClass('selected')) {
            $(this).removeClass('selected');
            $('#button_pause').attr('disabled', 'disabled');
            $('#button_stop').attr('disabled', 'disabled');
        } else {
            stratinRecords.$('tr.selected').removeClass('selected');
            $(this).addClass('selected');
            $('#button_pause').attr('disabled', false);
            $('#button_stop').attr('disabled', false);
        }
    });


   //button get historical trades
   $('#bt-trade').click(function () {
    event.preventDefault();
    $('#bt-trade').attr('disabled','disabled');
    $( "#trades-data").addClass("in");

    localStorage.setItem("trade_timestamp",$('#trade-timestamp').val());
    localStorage.setItem("trade_count",$('#trade-count').val());
    localStorage.setItem("trade_symbol",$('#trade-symbol').val());
    localStorage.setItem("trade_minsize",$('#trade-minsize').val());
    localStorage.setItem("trade_filter",$('#trade-filter').val());

    const rec = new Object()
    rec.timestamp_from = parseFloat($('#trade-timestamp').val())-parseInt($('#trade-count').val())
    rec.timestamp_to = parseFloat($('#trade-timestamp').val())+parseInt($('#trade-count').val())
    symbol = $('#trade-symbol').val()
    //jsonString = JSON.stringify(rec);
    //alert(JSON.stringify(rec))
    $.ajax({
        url:"/tradehistory/"+symbol+"/",
        beforeSend: function (xhr) {
            xhr.setRequestHeader('X-API-Key',
            API_KEY); },
        method:"GET",
        contentType: "application/json",
        dataType: "json",
        data: rec,
        success:function(data){							
            $('#bt-trade').attr('disabled', false);
            $('#trades-data').show();
            //$('#trades-data').text("")
            var minsize = parseInt($('#trade-minsize').val());
            //filter string to filter array
            var valueInserted = $("#trade-filter").val(); // "tag1,tag2,tag3, "two words""
            var filterList = valueInserted.split(",");  // ["tag1", "tag2", "tag3", "two words"]
            for (var i in filterList) {
                filterList[i] = filterList[i].trim();
            }

            console.log("filter list")
            console.log(filterList)
            console.log(minsize)
            var row = ""
            var puvodni = parseFloat($('#trade-timestamp').val())
            $('#trades-data-table').html(row);
            data.forEach((tradeLine) => {
                //console.log(JSON.stringify(tradeLine))
                date = new Date(tradeLine.timestamp)
                timestamp = date.getTime()/1000

                //trade contains filtered condition
                bg = (findCommonElements3(filterList, tradeLine.conditions) ? 'style="background-color: #e6e6e6;"' : '')

                row += '<tr role="row" '+ ((timestamp == puvodni) ? 'class="selected"' : '') +' ' + bg + '><td>' + timestamp + '</td><td>' + tradeLine.price + '</td>' +
                            '<td>' + tradeLine.size + '</td><td>' + tradeLine.id + '</td>' +
                            '<td>' + tradeLine.conditions + '</td><td>' + tradeLine.tape + '</td>' +
                            '<td>' + tradeLine.timestamp + '</td></tr>';
            
            });
            //console.log(row);
            $('#trades-data-table').html(row);
            // $('#trades-data').html(row)
        },
        error: function(xhr, status, error) {
            var err = eval("(" + xhr.responseText + ")");
            window.alert(JSON.stringify(xhr));
            console.log(JSON.stringify(xhr));
            $('#bt-trade').attr('disabled', false);
        }
    })
});

    //button refresh
    $('#button_refresh').click(function () {
        runnerRecords.ajax.reload();
        stratinRecords.ajax.reload();
    })

    //button copy
    $('#button_copy').click(function () {
        event.preventDefault();
        $('#button_copy').attr('disabled','disabled');
        row = stratinRecords.row('.selected').data();
        const rec = new Object()
        rec.id2 = parseInt(row.id2);
        rec.name = row.name;
        rec.symbol = row.symbol;
        rec.class_name = row.class_name;
        rec.script = row.script;
        rec.open_rush = row.open_rush;
        rec.close_rush = row.close_rush;
        rec.stratvars_conf = row.stratvars_conf;
        rec.add_data_conf = row.add_data_conf;
        rec.note = row.note;
        rec.history = "";
        jsonString = JSON.stringify(rec);
        navigator.clipboard.writeText(jsonString);
        $('#button_copy').attr('disabled', false);
    })

   //button duplicate
   $('#button_dup').click(function () {
    row = stratinRecords.row('.selected').data();
    event.preventDefault();
    $('#button_dup').attr('disabled','disabled');
    const rec = new Object()
    rec.id2 = parseInt(row.id2) + 1;
    rec.name = row.name + " copy";
    rec.symbol = row.symbol;
    rec.class_name = row.class_name;
    rec.script = row.script;
    rec.open_rush = row.open_rush;
    rec.close_rush = row.close_rush;
    rec.stratvars_conf = row.stratvars_conf;
    rec.add_data_conf = row.add_data_conf;
    rec.note = row.note;
    rec.history = "";
    jsonString = JSON.stringify(rec);
    $.ajax({
        url:"/stratins/",
        beforeSend: function (xhr) {
            xhr.setRequestHeader('X-API-Key',
            API_KEY); },
        method:"POST",
        contentType: "application/json",
        dataType: "json",
        data: jsonString,
        success:function(data){							
            $('#button_dup').attr('disabled', false);
            stratinRecords.ajax.reload();
        },
        error: function(xhr, status, error) {
            var err = eval("(" + xhr.responseText + ")");
            window.alert(JSON.stringify(xhr));
            console.log(JSON.stringify(xhr));
            $('#button_dup').attr('disabled', false);
        }
    })
});

    //button pause
    $('#button_pause').click(function () {
        row = runnerRecords.row('.selected').data();
        event.preventDefault();
        $('#button_pause').attr('disabled','disabled');
        $.ajax({
            url:"/stratins/"+row.id+"/pause",
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-API-Key',
                API_KEY); },
            method:"PUT",
            contentType: "application/json",
            dataType: "json",
            success:function(data){							
                $('#button_pause').attr('disabled', false);
                runnerRecords.ajax.reload();
                stratinRecords.ajax.reload();
            },
            error: function(xhr, status, error) {
                var err = eval("(" + xhr.responseText + ")");
                window.alert(JSON.stringify(xhr));
                console.log(JSON.stringify(xhr));
                $('#button_pause').attr('disabled', false);
            }
        })
    });

    //button stop
    $('#button_stop').click(function () {
        row = runnerRecords.row('.selected').data();
        event.preventDefault();
        $('#button_stop').attr('disabled','disabled');
        $.ajax({
            url:"/stratins/"+row.id+"/stop",
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-API-Key',
                    API_KEY); },
            method:"PUT",
            contentType: "application/json",
            dataType: "json",
            success:function(data){							
                $('#button_stop').attr('disabled', false);
                setTimeout(function () {
                    runnerRecords.ajax.reload();
                    stratinRecords.ajax.reload();
                  }, 2300)
            },
            error: function(xhr, status, error) {
                var err = eval("(" + xhr.responseText + ")");
                window.alert(JSON.stringify(xhr));
                console.log(JSON.stringify(xhr));
                $('#button_stop').attr('disabled', false);
            }
        })
    });

    //button stop all
    $('#button_stopall').click(function () {
        event.preventDefault();
        $('#buttonall_stop').attr('disabled','disabled');
        $.ajax({
            url:"/stratins/stop",
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-API-Key',
                    API_KEY); },
            method:"PUT",
            contentType: "application/json",
            dataType: "json",
            success:function(data){							
                $('#button_stopall').attr('disabled', false);
                setTimeout(function () {
                    runnerRecords.ajax.reload();
                    stratinRecords.ajax.reload();
                  }, 2300)
            },
            error: function(xhr, status, error) {
                var err = eval("(" + xhr.responseText + ")");
                window.alert(JSON.stringify(xhr));
                console.log(JSON.stringify(xhr));
                $('#button_stopall').attr('disabled', false);
            }
        })
    });


    //button run
    $('#button_run').click(function () {
        row = stratinRecords.row('.selected').data();
        window.$('#runModal').modal('show');
        $('#bt_from').val(localStorage.getItem("bt_from"));
        $('#bt_to').val(localStorage.getItem("bt_to"));
        $('#mode').val(localStorage.getItem("mode"));
        $('#account').val(localStorage.getItem("account"));
        $('#debug').val(localStorage.getItem("debug"));
        $('#runid').val(row.id);
    });

    //button add
    $('#button_add').click(function () {
        window.$('#recordModal').modal('show');
        $('#recordForm')[0].reset();
		$('.modal-title').html("<i class='fa fa-plus'></i> Add Record");
		$('#action').val('addRecord');
		$('#save').val('Add');
    });

    //edit button
    $('#button_edit').click(function () {
        row = stratinRecords.row('.selected').data();
        window.$('#recordModal').modal('show');
        $('#id').val(row.id);
        $('#id2').val(row.id2);
        $('#name').val(row.name);
        $('#symbol').val(row.symbol);
        $('#class_name').val(row.class_name);				
        $('#script').val(row.script);
        $('#open_rush').val(row.open_rush);
        $('#close_rush').val(row.close_rush);
        $('#stratvars_conf').val(row.stratvars_conf);
        $('#add_data_conf').val(row.add_data_conf);
        $('#note').val(row.note);
        $('#history').val(row.history);
        $('.modal-title').html(" Edit Records");
        $('#action').val('updateRecord');
        $('#save').val('Save');
    });
    //delete button
    $('#button_delete').click(function () {
        row = stratinRecords.row('.selected').data();
        window.$('#delModal').modal('show');
        $('#delid').val(row.id);
        $('#action').val('delRecord');
        $('#save').val('Delete');

    });
    //json add button
    $('#button_add_json').click(function () {
        window.$('#jsonModal').modal('show');
    });
} );

//stratin table
var stratinRecords = 
    $('#stratinTable').DataTable( {
        ajax: { 
            url: '/stratins/',
            dataSrc: '',
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-API-Key',
                    API_KEY); },
            error: function(xhr, status, error) {
                //var err = eval("(" + xhr.responseText + ")");
                //window.alert(JSON.stringify(xhr));
                console.log(JSON.stringify(xhr));
            }
            },
        columns: [{ data: 'id' },
                    {data: 'id2'},
                    {data: 'name'},
                    {data: 'symbol'},
                    {data: 'class_name'},
                    {data: 'script'},
                    {data: 'open_rush', visible: false},
                    {data: 'close_rush', visible: false},
                    {data: 'stratvars_conf', visible: false},
                    {data: 'add_data_conf', visible: false},
                    {data: 'note'},
                    {data: 'history', visible: false},
                    {data: 'id', visible: true}
                ],
        columnDefs: [{
            targets: 12,
            render: function ( data, type, row ) {
                var status = get_status(data)
                return '<i class="fas fa-check-circle">'+status+'</i>'
            },
            }],
        order: [[1, 'asc']],
        paging: false,
        // createdRow: function( row, data, dataIndex){
        //     if (is_running(data.id) ){
        //         alert("runner");
        //         $(row).addClass('highlight');
        //     }
        //}
        } );

//runner table
var runnerRecords = 
    $('#runnerTable').DataTable( {
        ajax: { 
            url: '/runners/',
            dataSrc: '',
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-API-Key',
                    API_KEY); },
            error: function(xhr, status, error) {
                //var err = eval("(" + xhr.responseText + ")");
                //window.alert(JSON.stringify(xhr));
                console.log(JSON.stringify(xhr));
            },
            // success:function(data){							
            //     if ( ! runnerRecords.data().count() ) {
            //         $('#button_stopall').attr('disabled', 'disabled');
            //     }
            //     else {
            //         $('#button_stopall').attr('disabled', false);
            //     }
            // },
            },
        columns: [{ data: 'id' },
                    {data: 'run_started'},
                    {data: 'run_mode'},
                    {data: 'run_account'},
                    {data: 'run_paused'}
                ],
        paging: false,
        processing: false
        } );

//modal na run
$("#runModal").on('submit','#runForm', function(event){
    localStorage.setItem("bt_from", $('#bt_from').val());
    localStorage.setItem("bt_to", $('#bt_to').val());
    localStorage.setItem("mode", $('#mode').val());
    localStorage.setItem("account", $('#account').val());
    localStorage.setItem("debug", $('#debug').val());
    event.preventDefault();
    $('#run').attr('disabled','disabled');
    
    var formData = $(this).serializeJSON();
    //rename runid to id
    Object.defineProperty(formData, "id", Object.getOwnPropertyDescriptor(formData, "runid"));
    delete formData["runid"];
    if (formData.bt_from == "") {delete formData["bt_from"];}
    if (formData.bt_to == "") {delete formData["bt_to"];}
    jsonString = JSON.stringify(formData);
    //window.alert(jsonString);
    $.ajax({
        url:"/stratins/"+formData.id+"/run",
        beforeSend: function (xhr) {
            xhr.setRequestHeader('X-API-Key',
                API_KEY); },
        method:"PUT",
        contentType: "application/json",
        data: jsonString,
        success:function(data){
            //pokud mame subscribnuto na RT                
            if ($('#subscribe').prop('checked')) {
                //subscribe input value gets id of current runner
                $('#runnerId').val($('#runid').val());
                $( "#bt-conn" ).trigger( "click" );
            }				
            $('#runForm')[0].reset();
            window.$('#runModal').modal('hide');				
            $('#run').attr('disabled', false);
            setTimeout(function () {
                runnerRecords.ajax.reload();
                stratinRecords.ajax.reload();
              }, 1500);
        },
        error: function(xhr, status, error) {
            var err = eval("(" + xhr.responseText + ")");
            window.alert(JSON.stringify(xhr));
            console.log(JSON.stringify(xhr));
            $('#run').attr('disabled', false);
        }

    })
});


//modal na add/edit
$("#recordModal").on('submit','#recordForm', function(event){
    if ($('#save').val() == "Add") {
        //code for add
        event.preventDefault();
        $('#save').attr('disabled','disabled');
        var formData = $(this).serializeJSON();
        jsonString = JSON.stringify(formData);
        $.ajax({
            url:"/stratins/",
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-API-Key',
                    API_KEY); },
            method:"POST",
            contentType: "application/json",
            dataType: "json",
            data: jsonString,
            success:function(data){				
                $('#recordForm')[0].reset();
                window.$('#recordModal').modal('hide');				
                $('#save').attr('disabled', false);
                setTimeout(function () {
                    runnerRecords.ajax.reload();
                    stratinRecords.ajax.reload();
                  }, 750)
            },
            error: function(xhr, status, error) {
                var err = eval("(" + xhr.responseText + ")");
                window.alert(JSON.stringify(xhr));
                console.log(JSON.stringify(xhr));
                $('#save').attr('disabled', false);
            }

        })
    }
    else {
        //code for edit
        event.preventDefault();
        $('#save').attr('disabled','disabled');
        var formData = $(this).serializeJSON();
        jsonString = JSON.stringify(formData);
        $.ajax({
            url:"/stratins/"+formData.id,
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-API-Key',
                    API_KEY); },
            method:"PATCH",
            contentType: "application/json",
            dataType: "json",
            data: jsonString,
            success:function(data){				
                $('#recordForm')[0].reset();
                window.$('#recordModal').modal('hide');				
                $('#save').attr('disabled', false);
                stratinRecords.ajax.reload();
            },
            error: function(xhr, status, error) {
                var err = eval("(" + xhr.responseText + ")");
                window.alert(JSON.stringify(xhr));
                console.log(JSON.stringify(xhr));
                $('#save').attr('disabled', false);
            }

        })
        
    }

});	

//add json modal
$("#jsonModal").on('submit','#jsonForm', function(event){
    event.preventDefault();
    $('#json_add').attr('disabled','disabled');
    jsonString = $('#jsontext').val();
    $.ajax({
        url:"/stratins/",
        beforeSend: function (xhr) {
            xhr.setRequestHeader('X-API-Key',
                API_KEY); },
        method:"POST",
        contentType: "application/json",
        dataType: "json",
        data: jsonString,
        success:function(data){				
            $('#jsonForm')[0].reset();
            window.$('#jsonModal').modal('hide');				
            $('#json_add').attr('disabled', false);
            setTimeout(function () {
                runnerRecords.ajax.reload();
                stratinRecords.ajax.reload();
                }, 750)
        },
        error: function(xhr, status, error) {
            var err = eval("(" + xhr.responseText + ")");
            window.alert(JSON.stringify(xhr));
            console.log(JSON.stringify(xhr));
            $('#json_add').attr('disabled', false);
        }
    })
});


//delete modal
$("#delModal").on('submit','#delForm', function(event){
        event.preventDefault();
        $('#delete').attr('disabled','disabled');
        var formData = $(this).serializeJSON();
        $.ajax({
            url:"/stratins/"+formData.delid,
            beforeSend: function (xhr) {
                xhr.setRequestHeader('X-API-Key',
                    API_KEY); },
            method:"DELETE",
            contentType: "application/json",
            dataType: "json",
            success:function(data){				
                $('#delForm')[0].reset();
                window.$('#delModal').modal('hide');				
                $('#delete').attr('disabled', false);
                stratinRecords.ajax.reload();
            },
            error: function(xhr, status, error) {
                var err = eval("(" + xhr.responseText + ")");
                window.alert(JSON.stringify(xhr));
                console.log(JSON.stringify(xhr));
                $('#delete').attr('disabled', false);
            }

        })
});
