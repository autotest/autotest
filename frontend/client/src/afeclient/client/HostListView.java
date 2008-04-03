package afeclient.client;

import com.google.gwt.user.client.ui.RootPanel;

public class HostListView extends TabView {
    protected static final int HOSTS_PER_PAGE = 30;
    
    public String getElementId() {
        return "hosts";
    }
    
    protected HostTable table = new RpcHostTable();
    protected HostTableDecorator hostTableDecorator = 
        new HostTableDecorator(table, HOSTS_PER_PAGE);
    
    public void initialize() {
        RootPanel.get("hosts_list").add(hostTableDecorator);
    }

    public void refresh() {
        super.refresh();
        table.refresh();
    }
}
