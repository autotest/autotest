package autotest.common.ui;

import autotest.common.CustomHistory;

import com.google.gwt.user.client.DOM;
import com.google.gwt.user.client.Element;
import com.google.gwt.user.client.ui.Composite;

/**
 * A widget to facilitate building a tab panel from elements present in the 
 * static HTML document.  Each <code>TabView</code> grabs a certain HTML
 * element, removes it from the document, and wraps it.  It can then be added
 * to a TabPanel.  The <code>getTitle()</code> method retrieves a title for the
 * tab from the "title" attribute of the HTML element.  This class also supports
 * lazy initialization of the tab by waiting until the tab is first displayed.
 */
public abstract class TabView extends Composite {
    public static final String HISTORY_PREFIX = "h_";
    protected boolean initialized = false;
    protected String title;
    
    public TabView() {
        Element thisTabElement = DOM.getElementById(getElementId());
        ElementWidget thisTab = new ElementWidget(thisTabElement);
        thisTab.removeFromDocument();
        initWidget(thisTab);
        title = DOM.getElementAttribute(thisTabElement, "title");
    }
    
    public void ensureInitialized() {
        if (!initialized) {
            initialize();
            initialized = true;
        }
    }
    
    // primarily for subclasses to override
    public void refresh() {}
    
    public void display() {
        ensureInitialized();
        refresh();
    }
    
    @Override
    public String getTitle() {
        return title;
    }
    
    public void updateHistory() {
        if (!this.getWidget().isVisible())
            return;
        CustomHistory.newItem(getHistoryToken());
    }
    
    public String getHistoryToken() {
        return HISTORY_PREFIX + getElementId();
    }
    
    /**
     * Should *not* trigger a refresh.  refresh() will be called separately.
     */
    public void handleHistoryToken(String token) {}
    
    public abstract void initialize();
    public abstract String getElementId();
}
