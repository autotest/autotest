package autotest.common.ui;

import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.DeckPanel;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.TabPanel;
import com.google.gwt.user.client.ui.VerticalPanel;

public class CustomTabPanel extends Composite {
    protected TabPanel tabPanel = new TabPanel();
    protected Panel otherWidgetsPanel = new HorizontalPanel();
    protected int topBarHeight = 0;
    
    public CustomTabPanel() {
        VerticalPanel container = new VerticalPanel();
        HorizontalPanel top = new HorizontalPanel();
        container.add(top);
        
        // put the TabBar at the top left
        top.add(tabPanel.getTabBar());
        top.setCellHeight(tabPanel.getTabBar(), "100%");
        tabPanel.getTabBar().setHeight("100%");
        
        // make a place for other widgets next to the tab bar
        top.add(otherWidgetsPanel);
        
        // put the TabPanel's DeskPanel below
        DeckPanel tabDeck = tabPanel.getDeckPanel();
        container.add(tabDeck);
        container.setCellHeight(tabDeck, "100%");
        
        initWidget(container);
    }

    public TabPanel getTabPanel() {
        return tabPanel;
    }

    public Panel getOtherWidgetsPanel() {
        return otherWidgetsPanel;
    }
}
