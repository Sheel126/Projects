package com.sheel.finance_ai.service;

import com.sheel.finance_ai.model.User;
import com.sheel.finance_ai.repository.UserRepository;
import org.springframework.stereotype.Service;
import java.util.List;

@Service
public class UserService {

    private final UserRepository repo;

    public UserService(UserRepository repo) {
        this.repo = repo;
    }

    public List<User> getAllUsers() {
        return repo.findAll();
    }

    public User saveUser(User user) {
        return repo.save(user);
    }
}
