package afeclient.client;

import com.google.gwt.user.client.ui.RootPanel;

public class HostListView extends TabView {
    protected static final int HOSTS_PER_PAGE = 30;
    
    public String getElementId() {
        return "hosts";
    }
    
    protected HostTable hostTable = new HostTable(HOSTS_PER_PAGE);
    
    public void initialize() {
        hostTable.getHosts();
        RootPanel.get("hosts_list").add(hostTable);
    }
}
