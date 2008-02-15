package afeclient.client;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.SourcesTableEvents;
import com.google.gwt.user.client.ui.TableListener;

/**
 * A table to display jobs, including a summary of host queue entries.
 */
public class JobTable extends DataTable {
    public static final String HOSTS_SUMMARY = "hosts_summary";
    public static final String CREATED_TEXT = "created_text";
    
    interface JobTableListener {
        public void onJobClicked(int jobId);
    }

    protected JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();

    public static final String[][] JOB_COLUMNS = { { "id", "ID" },
            { "owner", "Owner" }, { "name", "Name" },
            { "priority", "Priority" }, { "control_type", "Client/Server" },
            { CREATED_TEXT, "Created" }, { HOSTS_SUMMARY, "Status" } };

    public JobTable(final JobTableListener listener) {
        super(JOB_COLUMNS);
        
        if (listener != null) {
            table.addTableListener(new TableListener() {
                public void onCellClicked(SourcesTableEvents sender, int row, int cell) {
                    int jobId = Integer.parseInt(table.getHTML(row, 0));
                    listener.onJobClicked(jobId);
                }
            });
        }
    }

    protected void preprocessRow(JSONObject row) {
        JSONObject counts = row.get("status_counts").isObject();
        String countString = Utils.formatStatusCounts(counts, "<br>");
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

    public void getJobs(JSONObject filterInfo) {
        rpcProxy.rpcCall("get_jobs_summary", filterInfo, new JsonRpcCallback() {
            public void onSuccess(JSONValue result) {
                clear();
                JSONArray jobs = result.isArray();
                addRows(jobs);
            }
        });
    }
}
