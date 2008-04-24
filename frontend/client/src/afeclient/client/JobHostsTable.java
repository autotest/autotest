package afeclient.client;

import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.ui.Widget;

import afeclient.client.table.DynamicTable;
import afeclient.client.table.Filter;

/**
 * A table to display host queue entries associated with a job.
 */
public class JobHostsTable extends DynamicTable {
    public static final String[][] JOB_HOSTS_COLUMNS = {
        {"host", "Host"}, {"status", "Status"}
    };
    
    protected int jobId;
    
    public JobHostsTable() {
        super(JOB_HOSTS_COLUMNS, 
              new JobStatusDataSource("get_host_queue_entries", 
                                      "get_num_host_queue_entries"));
        addFilter(new Filter() {
            public void addParams(JSONObject params) {
                params.put("job", new JSONNumber(jobId));
            }

            public Widget getWidget() {
                return null;
            }

            public boolean isActive() {
                return true;
            } 
        });
    }
    
    public void setJobId(int jobId) {
        this.jobId = jobId;
        refresh();
    }
}
