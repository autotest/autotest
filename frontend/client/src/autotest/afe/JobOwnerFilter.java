package autotest.afe;

import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.table.FieldFilter;
import autotest.common.ui.ExtendedListBox;

import com.google.gwt.event.dom.client.ChangeEvent;
import com.google.gwt.event.dom.client.ChangeHandler;
import com.google.gwt.event.logical.shared.ValueChangeEvent;
import com.google.gwt.event.logical.shared.ValueChangeHandler;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.RadioButton;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;


public class JobOwnerFilter extends FieldFilter 
                            implements ValueChangeHandler<Boolean>, ChangeHandler {
    private static int nameCounter = 0;

    private ExtendedListBox userList = new ExtendedListBox();
    private RadioButton allUsersRadio, selectUserRadio;
    private Panel parentPanel;

    public JobOwnerFilter(String field) {
        super(field);
        String radioGroupName = getFreshName();
        allUsersRadio = new RadioButton(radioGroupName, "All users");
        selectUserRadio = new RadioButton(radioGroupName);
        allUsersRadio.addValueChangeHandler(this);
        selectUserRadio.addValueChangeHandler(this);

        populateUserList();
        userList.addChangeHandler(this);

        Panel selectUserPanel = new HorizontalPanel();
        selectUserPanel.add(selectUserRadio);
        selectUserPanel.add(userList);
        parentPanel = new VerticalPanel();
        parentPanel.add(allUsersRadio);
        parentPanel.add(selectUserPanel);

        selectUserRadio.setValue(true);
    }

    @Override
    // radio button selection changes
    public void onValueChange(ValueChangeEvent<Boolean> event) {
        userList.setEnabled(event.getSource() == selectUserRadio);
        notifyListeners();
    }

    @Override
    // user list changes
    public void onChange(ChangeEvent event) {
        notifyListeners();
    }

    private static String getFreshName() {
        nameCounter++;
        return "JobOwnerFilter" + Integer.toString(nameCounter);
    }

    private void populateUserList() {
        StaticDataRepository staticData = StaticDataRepository.getRepository();
        JSONArray userArray = staticData.getData("users").isArray();
        for (String user : Utils.JSONObjectsToStrings(userArray, "login")) {
            userList.addItem(user);
        }
        String currentUser = staticData.getCurrentUserLogin();
        userList.selectByName(currentUser);
    }

    @Override
    public JSONValue getMatchValue() {
        assert selectUserRadio.getValue();
        return new JSONString(userList.getSelectedName());
    }

    @Override
    public Widget getWidget() {
        return parentPanel;
    }

    @Override
    public boolean isActive() {
        return selectUserRadio.getValue();
    }
}
