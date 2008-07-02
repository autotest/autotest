package autotest.common.table;

import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.KeyboardListener;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.Widget;

public class SearchFilter extends FieldFilter {
    public TextBox searchBox = new TextBox();
    
    public SearchFilter(String fieldName) {
        super(fieldName);
        searchBox.setStylePrimaryName("filter-box");
        searchBox.addKeyboardListener(new KeyboardListener() {
            public void onKeyPress(Widget sender, char keyCode, int modifiers) {}
            public void onKeyDown(Widget sender, char keyCode, int modifiers) {}
            public void onKeyUp(Widget sender, char keyCode, int modifiers) {
                notifyListeners();
            }
        });
    }

    @Override
    public JSONValue getMatchValue() {
        return new JSONString(searchBox.getText());
    }

    @Override
    public boolean isActive() {
        return !searchBox.getText().equals("");
    }

    @Override
    public Widget getWidget() {
        return searchBox;
    }
}