package autotest.afe;

import autotest.common.table.DynamicTable;
import autotest.common.table.RpcDataSource;
import autotest.common.table.SelectionManager;
import autotest.common.table.TableClickWidget;
import autotest.common.table.DataSource.SortDirection;
import autotest.common.table.TableClickWidget.TableWidgetClickListener;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.Widget;

/**
 * A table to display jobs, including a summary of host queue entries.
 */
public class JobTable extends DynamicTable {
    public static final String HOSTS_SUMMARY = "hosts_summary";
    public static final String CREATED_TEXT = "created_text";


    private TableWidgetClickListener widgetListener = new TableWidgetClickListener() {
        public void onClick(TableClickWidget widget) {
            availableSelection.toggleSelected(getRow(widget.getRow()));
            availableSelection.refreshSelection();
        }
    };

    protected SelectionManager availableSelection;
    
    private TableWidgetFactory widgetFactory = new TableWidgetFactory() {
        public Widget createWidget(int row, int cell, JSONObject rowObject) {
            CheckBox checkBox = new CheckBox();
            if(availableSelection.getSelectedObjects().contains(rowObject)) {
                checkBox.setChecked(true);
            }
            return new TableClickWidget(checkBox, widgetListener, row, cell);
        }
    };
    
    private static final String[][] JOB_COLUMNS = { {CLICKABLE_WIDGET_COLUMN, "Select"}, 
            { "id", "ID" }, { "owner", "Owner" }, { "name", "Name" },
            { "priority", "Priority" }, { "control_type", "Client/Server" },
            { CREATED_TEXT, "Created" }, { HOSTS_SUMMARY, "Status" } };

    public JobTable() {
        super(JOB_COLUMNS, new RpcDataSource("get_jobs_summary", "get_num_jobs"));
        setWidgetFactory(widgetFactory);
        sortOnColumn("id", SortDirection.DESCENDING);
        
        availableSelection = new SelectionManager(this, false);
    }
    
    public SelectionManager getSelectionManager() {
        return availableSelection;
    }
    
    @Override
    protected void preprocessRow(JSONObject row) {
        JSONObject counts = row.get("status_counts").isObject();
        String countString = AfeUtils.formatStatusCounts(counts, "<br>");
        row.put(HOSTS_SUMMARY, new JSONString(countString));
        
        // remove seconds from created time
        JSONValue createdValue = row.get("created_on");
        String created = "";
        if (createdValue.isNull() == null) {
            created = createdValue.isString().stringValue();
            created = created.substring(0, created.length() - 3);
        }
        row.put(CREATED_TEXT, new JSONString(created));
    }
}
