package afeclient.client;

import afeclient.client.table.SimpleFilter;

import com.google.gwt.json.client.JSONValue;

/**
 * A table to display hosts.
 */
public class RpcHostTable extends HostTable {
    public RpcHostTable() {
        super(new HostDataSource());
        sortOnColumn("Hostname");
        SimpleFilter aclFilter = new SimpleFilter();
        JSONValue user = StaticDataRepository.getRepository().getData("user_login");
        aclFilter.setParameter("acl_group__users__login", user);
        addFilter(aclFilter);
    }
}
