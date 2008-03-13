package afeclient.client;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

/**
 * A table to display hosts.
 */
public class HostTable extends DynamicTable {
    protected static final String LOCKED_TEXT = "locked_text";
    public static final String[][] HOST_COLUMNS = {
        {"hostname", "Hostname"}, {"platform", "Platform"}, 
        {"status", "Status"}, {LOCKED_TEXT, "Locked"}
    };
    
    protected static JSONArray hosts = null;
    
    protected static final JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    
    public HostTable(int hostsPerPage) {
        super(HOST_COLUMNS);
        makeClientSortable();
        
        String[] searchColumns = {"Hostname"};
        addSearchBox(searchColumns, "Hostname:");
        addColumnFilter("Platform");
        addColumnFilter("Status");
        addColumnFilter("Locked");
        
        addPaginator(hostsPerPage);
    }
    
    protected void preprocessRow(JSONObject row) {
        super.preprocessRow(row);
        boolean locked = row.get("locked").isNumber().getValue() > 0;
        String lockedText = locked ? "Yes" : "No";
        row.put(LOCKED_TEXT, new JSONString(lockedText));
    }
    
    public void getHosts() {
        clear();
        JsonRpcCallback handleHosts = new JsonRpcCallback() {
            public void onSuccess(JSONValue result) {
                hosts = result.isArray();
                addRows(hosts);
                sortOnColumn(0);
                updateData();
            }
        };
        
        if(hosts == null) {
            JSONObject params = new JSONObject();
            JSONValue user = StaticDataRepository.getRepository().getData(
                "user_login");
            params.put("user", user);
            rpcProxy.rpcCall("get_hosts_acld_to", params, handleHosts);
        }
        else
            handleHosts.onSuccess(hosts);
    }
}
