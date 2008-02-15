package afeclient.client;

import java.util.Iterator;
import java.util.Set;

import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

/**
 * A table to display host queue entries associated with a job.
 */
public class JobHostsTable extends DynamicTable {
    public static final int HOSTS_PER_PAGE = 30;
    
    protected JsonRpcProxy rpcProxy;
    
    public static final String[][] JOB_HOSTS_COLUMNS = {
        {"hostname", "Host"}, {"status", "Status"}
    };
    
    public JobHostsTable(JsonRpcProxy proxy) {
        super(JOB_HOSTS_COLUMNS);
        this.rpcProxy = proxy;
        
        makeClientSortable();
        
        String[] searchColumns = {"Host"};
        addSearchBox(searchColumns, "Hostname:");
        addColumnFilter("Status");
        addPaginator(HOSTS_PER_PAGE);
    }
    
    public void getHosts(int jobId) {
        clear();
        JSONObject params = new JSONObject();
        params.put("id", new JSONNumber(jobId));
        rpcProxy.rpcCall("job_status", params, new JsonRpcCallback() {
            public void onSuccess(JSONValue result) {
                JSONObject resultObj = result.isObject();
                Set hostnames = resultObj.keySet();
                for(Iterator i = hostnames.iterator(); i.hasNext(); ) {
                    String host = (String) i.next();
                    JSONObject hostData = resultObj.get(host).isObject();
                    String status = hostData.get("status").isString().stringValue();
                    JSONValue metaCountValue = hostData.get("meta_count");
                    if (metaCountValue.isNull() == null) {
                        int metaCount = (int) metaCountValue.isNumber().getValue();
                        host += " (label)";
                        status = Integer.toString(metaCount) + " unassigned";
                    }
                    
                    JSONObject row = new JSONObject();
                    row.put("hostname", new JSONString(host));
                    row.put("status", new JSONString(status));
                    addRow(row);
                }
                
                sortOnColumn(0);
                updateData();
            }
        });
    }
}
