package autotest.afe;

import autotest.common.table.DynamicTable.DynamicTableListener;
import autotest.common.ui.TabView;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.ui.RootPanel;

public class HostListView extends TabView {
    protected static final int HOSTS_PER_PAGE = 30;
    
    public interface HostListListener {
        public void onHostSelected(String hostname);
    }
    
    protected HostListListener listener = null;
    
    public HostListView(HostListListener listener) {
        this.listener = listener;
    }

    @Override
    public String getElementId() {
        return "hosts";
    }
    
    protected HostTable table = new RpcHostTable();
    protected HostTableDecorator hostTableDecorator = 
        new HostTableDecorator(table, HOSTS_PER_PAGE);
    
    @Override
    public void initialize() {
        table.setClickable(true);
        table.addListener(new DynamicTableListener() {
            public void onRowClicked(int rowIndex, JSONObject row) {
                String hostname = row.get("hostname").isString().stringValue();
                listener.onHostSelected(hostname);
            }
            
            public void onTableRefreshed() {}
        });
        
        RootPanel.get("hosts_list").add(hostTableDecorator);
    }

    @Override
    public void refresh() {
        super.refresh();
        table.refresh();
    }
}
