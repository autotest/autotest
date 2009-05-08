package autotest.afe;

import autotest.common.table.DynamicTable;
import autotest.common.table.RpcDataSource;
import autotest.common.table.DataSource.SortDirection;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;

/**
 * A table to display jobs, including a summary of host queue entries.
 */
public class JobTable extends DynamicTable {
    public static final String HOSTS_SUMMARY = "hosts_summary";
    public static final String CREATED_TEXT = "created_text";

    private static final String[][] JOB_COLUMNS = { {CLICKABLE_WIDGET_COLUMN, "Select"}, 
            { "id", "ID" }, { "owner", "Owner" }, { "name", "Name" },
            { "priority", "Priority" }, { "control_type", "Client/Server" },
            { CREATED_TEXT, "Created" }, { HOSTS_SUMMARY, "Status" } };

    public JobTable() {
        super(JOB_COLUMNS, new RpcDataSource("get_jobs_summary", "get_num_jobs"));
        sortOnColumn("id", SortDirection.DESCENDING);
    }
    
    @Override
    protected void preprocessRow(JSONObject row) {
        JSONObject counts = row.get("status_counts").isObject();
        String countString = AfeUtils.formatStatusCounts(counts, "\n");
        row.put(HOSTS_SUMMARY, new JSONString(countString));
        
        // remove seconds from created time
        AfeUtils.removeSecondsFromDateField(row, "created_on", CREATED_TEXT);
    }
}
