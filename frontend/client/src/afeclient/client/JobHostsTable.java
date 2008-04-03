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
        {"hostname", "Host"}, {"status", "Status"}
    };
    
    protected int jobId;
    
    public JobHostsTable() {
        super(JOB_HOSTS_COLUMNS, 
              new JobStatusDataSource("job_status", "job_num_entries"));
        addFilter(new Filter() {
            public void addParams(JSONObject params) {
                params.put("job_id", new JSONNumber(jobId));
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
