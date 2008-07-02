package autotest.common.table;

import com.google.gwt.user.client.ui.SourcesTabEvents;
import com.google.gwt.user.client.ui.TabBar;
import com.google.gwt.user.client.ui.TabListener;
import com.google.gwt.user.client.ui.Widget;

public abstract class LinkSetFilter extends Filter implements TabListener {
    protected TabBar linkBar = new TabBar();
    protected boolean enableNotification = true;
    
    public LinkSetFilter() {
        linkBar.setStyleName("job-filter-links");
        linkBar.addTabListener(this);
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

    public void onTabSelected(SourcesTabEvents sender, int tabIndex) {
        if (enableNotification)
            notifyListeners();
    }

    public boolean onBeforeTabSelected(SourcesTabEvents sender, int tabIndex) {
        return true;
    }
}