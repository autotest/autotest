package autotest.common.table;

import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.FlowPanel;
import com.google.gwt.user.client.ui.KeyboardListener;
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
            searchButton.addClickListener(new ClickListener() {
                public void onClick(Widget sender) {
                    notifyListeners();
                }
            });
        }

        searchBox.addKeyboardListener(new KeyboardListener() {
            public void onKeyPress(Widget sender, char keyCode, int modifiers) {}
            public void onKeyDown(Widget sender, char keyCode, int modifiers) {}
            public void onKeyUp(Widget sender, char keyCode, int modifiers) {
                if (keyCode == KEY_ENTER || isIncremental) {
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