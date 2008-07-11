package autotest.common.ui;

import autotest.common.CustomHistory;

import com.google.gwt.user.client.History;
import com.google.gwt.user.client.HistoryListener;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.DeckPanel;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.SourcesTabEvents;
import com.google.gwt.user.client.ui.TabListener;
import com.google.gwt.user.client.ui.TabPanel;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class CustomTabPanel extends Composite implements HistoryListener {
    protected TabPanel tabPanel = new TabPanel();
    protected Panel otherWidgetsPanel = new HorizontalPanel();
    private Panel commonAreaPanel = new VerticalPanel();
    protected Button refreshButton = new Button("Refresh");
    protected int topBarHeight = 0;
    protected List<TabView> tabViews = new ArrayList<TabView>();
    
    public CustomTabPanel() {
        VerticalPanel container = new VerticalPanel();
        HorizontalPanel top = new HorizontalPanel();
        VerticalPanel bottom = new VerticalPanel();
        container.add(top);
        container.add(bottom);
        
        // put the TabBar at the top left
        top.add(tabPanel.getTabBar());
        top.setCellHeight(tabPanel.getTabBar(), "100%");
        tabPanel.getTabBar().setHeight("100%");
        
        // make a place for other widgets next to the tab bar
        top.add(otherWidgetsPanel);
        
        // put a common area above the tab deck
        bottom.add(commonAreaPanel);
        
        // put the TabPanel's DeckPanel below
        DeckPanel tabDeck = tabPanel.getDeckPanel();
        bottom.add(tabDeck);
        bottom.setCellHeight(tabDeck, "100%");
        
        tabPanel.addTabListener(new TabListener() {
            public boolean onBeforeTabSelected(SourcesTabEvents sender,
                                               int tabIndex) {
                // do nothing if the user clicks the selected tab
                if (tabPanel.getTabBar().getSelectedTab() == tabIndex)
                    return false;
                tabViews.get(tabIndex).ensureInitialized();
                tabViews.get(tabIndex).display();
                return true;
            }
            public void onTabSelected(SourcesTabEvents sender, int tabIndex) {
                tabViews.get(tabIndex).updateHistory();
            }
        });
        
        // transfer the DeckPanel's class to the entire bottom panel
        String tabDeckClass = tabDeck.getStyleName();
        tabDeck.setStyleName("");
        bottom.setStyleName(tabDeckClass);
        
        refreshButton.addClickListener(new ClickListener() {
            public void onClick(Widget sender) {
                getSelectedTabView().refresh();
            } 
        });
        otherWidgetsPanel.add(refreshButton);
        
        CustomHistory.addHistoryListener(this);
        
        container.setStyleName("custom-tab-panel");
        initWidget(container);
    }
    
    /**
     * This must be called after this widget has been added to the page.
     */
    public void initialize() {
        String initialToken = History.getToken();
        if (!initialToken.equals("")) {
            onHistoryChanged(initialToken);
        }
        
        // if the history token didn't provide a selected tab, default to the 
        // first tab
        if (getSelectedTabView() == null)
            tabPanel.selectTab(0);
    }
    
    public void addTabView(TabView tabView) {
        tabViews.add(tabView);
        tabPanel.add(tabView, tabView.getTitle());
    }
    
    public List<TabView> getTabViews() {
        return Collections.unmodifiableList(tabViews);
    }
    
    public TabView getSelectedTabView() {
        int selectedTab = tabPanel.getTabBar().getSelectedTab();
        if (selectedTab == -1)
            return null;
        return tabViews.get(selectedTab);
    }
    
    public void selectTabView(TabView tabView) {
        for (int i = 0; i < tabViews.size(); i++) {
            if (tabViews.get(i) == tabView) {
                tabPanel.selectTab(i);
                return;
            }
        }
        
        throw new IllegalArgumentException("Tab not found");
    }

    public TabPanel getTabPanel() {
        return tabPanel;
    }

    public Panel getOtherWidgetsPanel() {
        return otherWidgetsPanel;
    }
    
    public Panel getCommonAreaPanel() {
        return commonAreaPanel;
    }

    public void onHistoryChanged(String historyToken) {
        if (!historyToken.startsWith(TabView.HISTORY_PREFIX))
            return;
        
        // remove prefix
        historyToken = historyToken.substring(TabView.HISTORY_PREFIX.length());
        for (TabView tabView : tabViews) {
            String tabId = tabView.getElementId();
            if (historyToken.startsWith(tabId)) {
                tabView.ensureInitialized();
                
                int prefixLength = tabId.length() + 1;
                if (historyToken.length() > prefixLength) {
                    String restOfToken = historyToken.substring(prefixLength);
                    tabView.handleHistoryToken(restOfToken);
                }
                
                if (getSelectedTabView() != tabView)
                    selectTabView(tabView);
                else
                    tabView.refresh();
                
                return;
            }
        }
    }
}
