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
    protected static final String OTHER_LABELS = "other_labels";
    public static final String[][] HOST_COLUMNS = {
        {"hostname", "Hostname"}, {"platform", "Platform"}, 
        {OTHER_LABELS, "Other labels"}, {"status", "Status"}, 
        {LOCKED_TEXT, "Locked"}
    };
    
    protected static JSONArray hosts = null;
    
    protected static final JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    
    public HostTable(int hostsPerPage) {
        super(HOST_COLUMNS);
        makeClientSortable();
        
        StaticDataRepository staticData = StaticDataRepository.getRepository();
        JSONArray labels = staticData.getData("labels").isArray();
        String[] labelStrings = Utils.JSONtoStrings(labels);
        
        String[] searchColumns = {"Hostname"};
        addSearchBox(searchColumns, "Hostname:");
        addColumnFilter("Platform");
        addColumnFilter("Other labels", labelStrings, false);
        addColumnFilter("Status");
        addColumnFilter("Locked");
        
        addPaginator(hostsPerPage);
    }
    
    protected void preprocessRow(JSONObject row) {
        super.preprocessRow(row);
        boolean locked = row.get("locked").isNumber().getValue() > 0;
        String lockedText = locked ? "Yes" : "No";
        row.put(LOCKED_TEXT, new JSONString(lockedText));
        
        JSONString jsonPlatform = row.get("platform").isString();
        String platform = "";
        if (jsonPlatform != null)
            platform = jsonPlatform.stringValue();
        JSONArray labels = row.get("labels").isArray();
        String labelString = "";
        for (int i = 0; i < labels.size(); i++) {
            String label = labels.get(i).isString().stringValue();
            if (label.equals(platform))
                continue;
            if (!labelString.equals(""))
                labelString += ", ";
            labelString += label;
        }
        row.put(OTHER_LABELS, new JSONString(labelString));
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
