package afeclient.client;

import afeclient.client.table.Filter;
import afeclient.client.table.RpcDataSource;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Widget;

/**
 * A table to display hosts.
 */
public class RpcHostTable extends HostTable {
    class ACLFilter extends Filter {
        JSONValue user;
        
        public ACLFilter() {
            user = StaticDataRepository.getRepository().getData("user_login");
        }
        
        public void addParams(JSONObject params) {
            params.put("acl_group__users__login", user);
        }

        public Widget getWidget() {
            return null;
        }

        public boolean isActive() {
            return true;
        }
    }
    
    protected static final JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    
    public RpcHostTable() {
        super(new RpcDataSource("get_hosts", "get_num_hosts"));
        sortOnColumn("Hostname");
        addFilter(new ACLFilter());
    }
}
