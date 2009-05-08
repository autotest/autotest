package autotest.afe;

import autotest.common.table.DynamicTable;
import autotest.common.table.RpcDataSource;
import autotest.common.table.DataSource.SortDirection;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;

/**
 * A table to display scheduled runs.
 */
public class RecurringTable extends DynamicTable {
    public static final String START_DATE_TEXT = "start_date";

    private static final String[][] RECURRING_COLUMNS = { 
                            {CLICKABLE_WIDGET_COLUMN, "Select"}, 
                            { "job_id", "Job ID" },
                            { "owner", "Owner" },
                            { START_DATE_TEXT, "Recurring start" }, 
                            { "loop_period", "Loop period" },
                            { "loop_count", "Loop count" }};

    public RecurringTable() {
        super(RECURRING_COLUMNS, new RpcDataSource("get_recurring",
                                                   "get_num_recurring"));
        sortOnColumn("id", SortDirection.DESCENDING);
    }
    
    @Override
    protected void preprocessRow(JSONObject row) {
        JSONObject job = row.get("job").isObject();
        int jobId = (int) job.get("id").isNumber().doubleValue();
        JSONObject owner = row.get("owner").isObject();
        row.put("job_id", new JSONString(Integer.toString(jobId)));
        row.put("owner", owner.get("login"));
        // remove seconds from start_date
        AfeUtils.removeSecondsFromDateField(row, "start_date", START_DATE_TEXT);
        
    }
}
