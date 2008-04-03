package afeclient.client.table;

import com.google.gwt.user.client.ui.SourcesTabEvents;
import com.google.gwt.user.client.ui.TabBar;
import com.google.gwt.user.client.ui.TabListener;
import com.google.gwt.user.client.ui.Widget;

public abstract class LinkSetFilter extends Filter implements TabListener {
    protected TabBar linkBar = new TabBar();
    
    public LinkSetFilter() {
        linkBar.setStyleName("job-filter-links");
        linkBar.addTabListener(this);
    }
    
    public void addLink(String text) {
        linkBar.addTab(text);
    }

    public Widget getWidget() {
        return linkBar;
    }
    
    public int getSelectedLink() {
        return linkBar.getSelectedTab();
    }
    
    public void setSelectedLink(int link) {
        linkBar.selectTab(link);
    }

    public void onTabSelected(SourcesTabEvents sender, int tabIndex) {
        notifyListeners();
    }

    public boolean onBeforeTabSelected(SourcesTabEvents sender, int tabIndex) {
        return true;
    }
}