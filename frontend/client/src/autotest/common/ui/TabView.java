package autotest.common.ui;

import autotest.common.CustomHistory;
import autotest.common.Utils;
import autotest.common.CustomHistory.HistoryToken;

import com.google.gwt.dom.client.Document;
import com.google.gwt.dom.client.Element;
import com.google.gwt.http.client.URL;
import com.google.gwt.user.client.Event;
import com.google.gwt.user.client.History;
import com.google.gwt.user.client.Window;
import com.google.gwt.user.client.ui.HTMLPanel;
import com.google.gwt.user.client.ui.Widget;

import java.util.Map;

/**
 * A widget to facilitate building a tab panel from elements present in the 
 * static HTML document.  Each <code>TabView</code> grabs a certain HTML
 * element, removes it from the document, and wraps it.  It can then be added
 * to a TabPanel.  The <code>getTitle()</code> method retrieves a title for the
 * tab from the "title" attribute of the HTML element.  This class also supports
 * lazy initialization of the tab by waiting until the tab is first displayed.
 */
public abstract class TabView {
    private boolean initialized = false;
    private HTMLPanel htmlPanel;
    private String title;
    protected boolean visible;
    private Map<String, String> savedState;

    public Widget getWidget() {
        return htmlPanel;
    }

    public void attachToDocument() {
        title = Document.get().getElementById(getElementId()).getAttribute("title");
        htmlPanel = Utils.divToPanel(getElementId());
    }
    
    public void addWidget(Widget widget, String subElementId) {
        htmlPanel.add(widget, subElementId);
    }
    
    public Element getElementById(String subElementId) {
        return htmlPanel.getElementById(subElementId);
    }

    // for subclasses to override
    public void initialize() {}

    public void ensureInitialized() {
        if (!initialized) {
            initialize();
            initialized = true;
        }
    }
    
    // for subclasses to override
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

    public String getTitle() {
        return title;
    }
    
    public void updateHistory() {
        CustomHistory.newItem(getHistoryArguments());
    }
    
    /**
     * Subclasses should override this to store any additional history information.
     */
    public HistoryToken getHistoryArguments() {
        HistoryToken arguments = new HistoryToken();
        arguments.put("tab_id", getElementId());
        return arguments;
    }
    
    /**
     * Subclasses should override this to actually handle the tokens.
     * Should *not* trigger a refresh.  refresh() will be called separately.
     * 
     * @param arguments the parsed history arguments to use
     */
    public void handleHistoryArguments(Map<String, String> arguments) {}

    public abstract String getElementId();

    protected void saveHistoryState() {
        savedState = getHistoryArguments();
    }

    protected void restoreHistoryState() {
        handleHistoryArguments(savedState);
    }

    protected void openHistoryToken(HistoryToken historyToken) {
        if (isOpenInNewWindowEvent()) {
            String newUrl = Window.Location.getPath() + "#" + historyToken;
            Utils.openUrlInNewWindow(URL.encode(newUrl));
        } else {
            History.newItem(historyToken.toString());
        }
    }

    private static boolean isOpenInNewWindowEvent() {
        Event event = Event.getCurrentEvent();
        boolean middleMouseButton = (event.getButton() & Event.BUTTON_MIDDLE) != 0;
        // allow control-click on windows or command-click on macs (control-click is overridden
        // on macs to take the place of right-click)
        return event.getCtrlKey() || event.getMetaKey() || middleMouseButton;
    }
}
