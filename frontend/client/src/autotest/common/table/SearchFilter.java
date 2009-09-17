package autotest.common.table;

import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.event.dom.client.KeyCodes;
import com.google.gwt.event.dom.client.KeyUpEvent;
import com.google.gwt.event.dom.client.KeyUpHandler;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.FlowPanel;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.Widget;

public class SearchFilter extends FieldFilter {
    private TextBox searchBox = new TextBox();
    private Button searchButton;
    private Panel container = new FlowPanel();
    
    private String activeSearch = "";
    
    public SearchFilter(String fieldName, final boolean isIncremental) {
        super(fieldName);
        setExactMatch(false);
        container.add(searchBox);
        searchBox.setStylePrimaryName("filter-box");

        if (!isIncremental) {
            searchButton = new Button("Search");
            container.add(searchButton);
            searchButton.addClickHandler(new ClickHandler() {
                public void onClick(ClickEvent event) {
                    notifyListeners();
                }
            });
        }

        searchBox.addKeyUpHandler (new KeyUpHandler() {
            public void onKeyUp(KeyUpEvent event) {
                if (event.getNativeKeyCode() == KeyCodes.KEY_ENTER || isIncremental) {
                    notifyListeners();
                }
            }
        });
    }

    @Override
    protected void notifyListeners() {
        activeSearch = searchBox.getText();
        super.notifyListeners();
    }

    @Override
    public JSONValue getMatchValue() {
        return new JSONString(activeSearch);
    }

    @Override
    public boolean isActive() {
        return !activeSearch.equals("");
    }

    @Override
    public Widget getWidget() {
        return container;
    }
}
