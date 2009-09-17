package autotest.common.table;

import com.google.gwt.event.logical.shared.SelectionEvent;
import com.google.gwt.event.logical.shared.SelectionHandler;
import com.google.gwt.user.client.ui.TabBar;
import com.google.gwt.user.client.ui.Widget;

public abstract class LinkSetFilter extends Filter implements SelectionHandler<Integer> {
    protected TabBar linkBar = new TabBar();
    protected boolean enableNotification = true;
    
    public LinkSetFilter() {
        linkBar.setStyleName("job-filter-links");
        linkBar.addSelectionHandler(this);
    }
    
    public void addLink(String text) {
        linkBar.addTab(text);
    }

    @Override
    public Widget getWidget() {
        return linkBar;
    }
    
    public int getSelectedLink() {
        return linkBar.getSelectedTab();
    }
    
    public void setSelectedLink(int link) {
        if (link != linkBar.getSelectedTab()) {
            enableNotification = false;
            linkBar.selectTab(link);
            enableNotification = true;
        }
    }
    
    @Override
    public void onSelection(SelectionEvent<Integer> event) {
        if (enableNotification)
            notifyListeners();
    }
}
