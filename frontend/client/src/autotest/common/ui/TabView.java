package autotest.common.ui;

import autotest.common.CustomHistory;
import autotest.common.Utils;

import com.google.gwt.user.client.ui.Composite;

import java.util.HashMap;
import java.util.Map;

/**
 * A widget to facilitate building a tab panel from elements present in the 
 * static HTML document.  Each <code>TabView</code> grabs a certain HTML
 * element, removes it from the document, and wraps it.  It can then be added
 * to a TabPanel.  The <code>getTitle()</code> method retrieves a title for the
 * tab from the "title" attribute of the HTML element.  This class also supports
 * lazy initialization of the tab by waiting until the tab is first displayed.
 */
public abstract class TabView extends Composite {
    protected boolean initialized = false;
    protected String title;
    protected boolean visible;
    
    public TabView() {
        ElementWidget thisTab = new ElementWidget(getElementId());
        initWidget(thisTab);
        title = thisTab.getElement().getAttribute("title");
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
        visible = true;
    }
    
    public void hide() {
        visible = false;
    }
    
    protected boolean isTabVisible() {
        return visible;
    }
    
    @Override
    public String getTitle() {
        return title;
    }
    
    public void updateHistory() {
        CustomHistory.newItem(getHistoryToken());
    }
    
    public String getHistoryToken() {
        return Utils.encodeUrlArguments(getHistoryArguments());
    }
    
    /**
     * Subclasses should override this to store any additional history information.
     */
    protected Map<String, String> getHistoryArguments() {
        Map<String, String> arguments = new HashMap<String, String>();
        arguments.put("tab_id", getElementId());
        return arguments;
    }
    
    /**
     * Subclasses should override this to actually handle the tokens.
     * Should *not* trigger a refresh.  refresh() will be called separately.
     */
    public void handleHistoryArguments(Map<String, String> arguments) {}
    
    public abstract void initialize();
    public abstract String getElementId();
}
